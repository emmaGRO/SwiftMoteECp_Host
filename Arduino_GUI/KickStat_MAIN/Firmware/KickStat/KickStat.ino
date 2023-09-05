
//Standard Arduino Libraries
#include <Wire.h>
//Custom External Libraries
#include "MemoryFree.h"
#include "pgmStrToRAM.h" //SerialDebugger.println(freeMemory(), DEC);  // print how much RAM is available.

//Custom Internal Libraries
#include "LMP91000.h"
#include "MiniStatAnalyst.h"

#include <String.h>
// basic file operations

#if defined(ARDUINO_ARCH_SAMD)
  #define SerialDebugger SerialUSB
#else
  #define SerialDebugger Serial
#endif


LMP91000 pStat = LMP91000();
MiniStatAnalyst analyst = MiniStatAnalyst();
const uint16_t arr_samples = 2500; //use 1000 for EIS, can use 2500 for other experiments
uint16_t arr_cur_index = 0;
int16_t volts[arr_samples] = {0};
float amps[arr_samples] = {0};
unsigned long input_time[arr_samples] = {0};
unsigned long output_time[arr_samples] = {0};

float v1_array[arr_samples] = {0};
float v2_array[arr_samples] = {0};


const uint16_t opVolt = 3300; //3300 mV
const uint8_t adcBits = 12;
const float v_tolerance = 0.008; //0.0075 works every other technique with 1mV step except CV which needs minimum 2mV step
const uint16_t dacResolution = pow(2,10)-1;


//LMP91000 control pins
const uint8_t dac = A0; 
const uint8_t MENB = 5;

//analog input pins to read voltages
const uint8_t LMP_C1 = A1;
const uint8_t LMP_C2 = A2;
const uint8_t LMP = A3;
const uint8_t anti_aliased = A4;


unsigned long lastTime = 0;
unsigned long realTime = 0;
uint16_t dacVout = 1500;

bool saveQueues = false;

//float RFB = 1494;

uint8_t bias_setting = 0;

//Test options
#define  CV "CV"  
#define SWV "SWV" 

uint8_t LMPgain   = 0;

// parameters for CV
//@param      Gain:    gain setting 
uint8_t CVgain   = 4;
//@param      Cycles:    Number of Cycles in the CV test
uint8_t CVCycles   = 3;
//@param      E1:     voltage to start the scan
int16_t CVE1    = 0;
//@param      E2:       voltage to stop the scan
int16_t CVE2      = 450;
//@param      Ep:      how much to increment the voltage by
int16_t CVEp     = 2;
//@param      vertex1:    edge of the scan. If vertex1 is greater than starting voltage, we start the experiment by running CV in the forward (oxidation) direction.
int16_t CVvertex1 = -250;
//@param      vertex2:    edge of the scan. If vertex2 is greater than starting voltage, we start the experiment by running CV in the reverse (reduction) direction
int16_t CVvertex2 = 400;
//@param      Frequency:       scanning Frequencyuency
double  CVFrequency      = 100;
//@param      setToZero:  Boolean determining whether the bias potential of the electrochemical cell should be set to 0 at the end of the experiment. 
bool    CVsetToZero = true;  
//@param      saveData:  Boolean determining whether to show the data on the serial monitor 
bool    CVsaveData  = true;
//@param      CVdesc:  Text explaining the test to run
String    CVdesc  = "CV test";

// parameters for SWV
//@param      Gain:    gain setting 
uint8_t SWVgain   = 4;
//@param      Cycles:    Number of Cycles in the CV test
uint8_t SWVCycles   = 1;
//@param      E1:     voltage to start the scan
int16_t SWVE1    = -300;
//@param      E2:       voltage to stop the scan
int16_t SWVE2      = 450;
//@param      Amplitude:   amplitude of square wave
int16_t SWVAmplitude  = 1;
//@param      Ep:      how much to increment the voltage by
int16_t SWVEp     = 1;
//@param      Frequency:       scanning Frequency
double  SWVFrequency      = 100;
//@param      setToZero:  Boolean determining whether the bias potential of the electrochemical cell should be set to 0 at the end of the experiment. 
bool    SWVsetToZero = true;  
//@param      saveData:  Boolean determining whether to show the data on the serial monitor 
bool    SWVsaveData  = true;
//@param      SWVdesc:  Text explaining the test to run
String    SWVdesc  = "SWV test";
//@param      RFB:  Feedback resistance value, only used when gain = 0
float RFB = 0;

bool running = true;
String testToRun;
void setup()
{
  Wire.begin();
  SerialDebugger.begin(115200);
  while(!SerialDebugger);

  analogReadResolution(12);
  analogWriteResolution(10);
  initADC(false);

  //enable the potentiostat
  pStat.setMENB(MENB);
  delay(50);
  pStat.standby();
  delay(50);
  initLMP(0);
  delay(2000); //warm-up time for the gas sensor
  running = false;
}


void loop()
{
  bool ready = false;
  String test;
  if (!running){
    String testToRun;
    while(!SerialDebugger.available()){
      }
    testToRun = SerialDebugger.readString();
    int len;
    String* t = split(testToRun,',',len);
    test = t[0];
    if (len > 2){
      for (int i=1; i <= len-1;i++){
        int len2;
        String* val = split(t[i],':',len2);
        changeValueofVariable(test, val[0],val[1]);
      }
      running = true;
      SerialDebugger.println(F("Test Starting"));
    }
    else{
      SerialDebugger.println(F("Error in test declaration")); 
    }
  }
  if (test == CV)
    {
      if(running){
        int vertex_offset = 10;
        runCV(CVgain, CVCycles, CVE1,CVE2,CVE1-vertex_offset,CVE2+vertex_offset,CVEp,CVFrequency,CVsetToZero,CVsaveData);
        running = false;
        SerialDebugger.println(F("Done")); 
      }        
    }
  else if (test == SWV)
    { 
      if(running){
        running = false;   
        runSWV(SWVgain, SWVE1, SWVE2, SWVAmplitude, SWVEp, SWVFrequency, SWVsetToZero,SWVsaveData);
        SerialDebugger.println(F("Done")); 
      }   
    }
  else{
    SerialDebugger.println(F("test not declared")); 
    running = false;
    }
}
void changeValueofVariable(String test, String variable,String value){
  if (test == "CV"){
    if(variable.equals("desc")){
      CVdesc = value;
    }
    if(variable.equals("Gain")){
      CVgain = atoi(value.c_str());
    }
    else if(variable.equals("Cycles")){
      CVCycles = atoi(value.c_str());
    }
    else if(variable.equals("E1")){
      CVE1 = atoi(value.c_str());
    }
    else if(variable.equals("E2")){
      CVE2 = atoi(value.c_str());
    }
    else if(variable.equals("vertex1")){
      CVvertex1 = atoi(value.c_str());
    }
    else if(variable.equals("vertex2")){
      CVvertex2 = atoi(value.c_str());
    }
    else if(variable.equals("Ep")){
      if (atoi(value.c_str())>=2){
        CVEp = atoi(value.c_str());
      }
      else{
        SerialDebugger.println("minimum value for step is 2");
        CVEp = 2;
      }
    }
    else if(variable.equals("Frequency")){
      CVFrequency = atoi(value.c_str());
    }
    else if(variable.equals("setToZero")){
      CVsetToZero = atoi(value.c_str());
    }
    else if(variable.equals("saveData")){
      CVsaveData = atoi(value.c_str());
    } 
    else{
      SerialDebugger.println("\t variable " + variable + " does not exist ");
      }   
  }
  if (test == "SWV"){
    if(variable.equals("desc")){
      SWVdesc = value;
    }
    if(variable.equals("Gain")){
      SWVgain = atoi(value.c_str());
    }
    else if(variable.equals("Cycles")){
      SWVCycles = atoi(value.c_str());
    }
    else if(variable.equals("E1")){
      SWVE1 = atoi(value.c_str());
    }
    else if(variable.equals("E2")){
      SWVE2 = atoi(value.c_str());
    }
    else if(variable.equals("Amplitude")){
      SWVAmplitude = atoi(value.c_str());
    }
    else if(variable.equals("Ep")){
      SWVEp = atoi(value.c_str());
    }
    else if(variable.equals("Frequency")){
      SWVFrequency = atoi(value.c_str());
    }
    else if(variable.equals("setToZero")){
      SWVsetToZero = atoi(value.c_str());
    }
    else if(variable.equals("saveData")){
      SWVsaveData = atoi(value.c_str());
    } 
    else if(variable.equals("Rtia")){
     RFB = atoi(value.c_str());
    }
    else if(variable.equals("Rload")){
      int16_t load = atoi(value.c_str());
      if (load == 10){pStat.setRLoad(LMP91000_RLOAD_10OHM);}
      else if (load == 33){pStat.setRLoad(LMP91000_RLOAD_33OHM);}
      else if (load == 50){pStat.setRLoad(LMP91000_RLOAD_50OHM);}
      else if (load == 100){pStat.setRLoad(LMP91000_RLOAD_100OHM);}
      else{SerialDebugger.println("\t RLoad does not exist ");} 
    }
    else{SerialDebugger.println("\t variable " + variable + " does not exist ");}   

  }
}

void printVoltsAndCurrent()
{
  SerialDebugger.println(F("Voltage,Current"));
  for(uint16_t i = 0; i < arr_samples; i++)
  {
    // stop the printing of empty data points
    bool stop = false;
    if(volts[i] == 0 && amps[i] == 0.00){      
      if(volts[i+1] == 0 && amps[i+1] == 0.00){
      stop = true;
      }
    }
    if (stop) break;
    else{
      String s = "Voltage: " + String(volts[i]) + ", Current: " + String(amps[i]) + "\n";
      SerialDebugger.print(s);
    }    
  }
}

String* split(String& v, char delimiter, int& length) {
  length = 1;
  bool found = false;

  // Figure out how many itens the array should have
  for (int i = 0; i < v.length(); i++) {
    if (v[i] == delimiter) {
      length++;
      found = true;
    }
  }
  // If the delimiter is found than create the array
  // and split the String
  if (found) {

    // Create array
    String* valores = new String[length];

    // Split the string into array
    int i = 0;
    for (int itemIndex = 0; itemIndex < length; itemIndex++) {
      for (; i < v.length(); i++) {
        if (v[i] == delimiter) {
          i++;
          break;
        }
        valores[itemIndex] += v[i];
      }
    }

    // Done, return the values
    return valores;
  }

  // No delimiter found
  return nullptr;
}
