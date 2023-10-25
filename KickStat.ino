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
uint16_t dacVout = 1500;

bool saveQueues = false;

//float RFB = 1494;

uint8_t bias_setting = 0;

//Test options
#define  CV 1  
#define SWV 2 
#define NPV 3
#define CA  4
#define DVP 5
#define AMP 6
#define EIS 7
#define CLOSE 9
// general parameters

uint8_t LMPgain   = 0;

// parameters for CV
//@param      Gain:    gain setting 
uint8_t CVgain   = 4;
//@param      cycles:    Number of cycles in the CV test
uint8_t CVcycles   = 3;
//@param      startV:     voltage to start the scan
int16_t CVstartV    = 0;
//@param      endV:       voltage to stop the scan
int16_t CVendV      = 450;
//@param      stepV:      how much to increment the voltage by
int16_t CVstepV     = 2;
//@param      vertex1:    edge of the scan. If vertex1 is greater than starting voltage, we start the experiment by running CV in the forward (oxidation) direction.
int16_t CVvertex1 = -250;
//@param      vertex2:    edge of the scan. If vertex2 is greater than starting voltage, we start the experiment by running CV in the reverse (reduction) direction
int16_t CVvertex2 = 400;
//@param      freq:       scanning frequency
double  CVfreq      = 100;
//@param      setToZero:  Boolean determining whether the bias potential of the electrochemical cell should be set to 0 at the end of the experiment. 
bool    CVsetToZero = true;  
//@param      saveData:  Boolean determining whether to show the data on the serial monitor 
bool    CVsaveData  = true;
//@param      CVdesc:  Text explaining the test to run
String    CVdesc  = "CV test";

// parameters for SWV
//@param      Gain:    gain setting 
uint8_t SWVgain   = 4;
//@param      cycles:    Number of cycles in the CV test
uint8_t SWVcycles   = 6;
//@param      startV:     voltage to start the scan
int16_t SWVstartV    = -300;
//@param      endV:       voltage to stop the scan
int16_t SWVendV      = 450;
//@param      pulseAmp:   amplitude of square wave
int16_t SWVpulseAmp  = 1;
//@param      stepV:      how much to increment the voltage by
int16_t SWVstepV     = 1;
//@param      freq:       scanning frequency
double  SWVfreq      = 100;
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
  if (!running){
    testToRun = "";
    SerialDebugger.println();
    SerialDebugger.println(F("Please select a test to run:"));
    SerialDebugger.println(F("\tCycloid Voltammetry:     1"));
    SerialDebugger.println(F("\tSquare Wave Voltammetry: 2"));
    // SerialDebugger.println(F("Normal Pulse Voltammetry: 3"));
    // SerialDebugger.println(F("Chronoamperometry: 4"));
    // SerialDebugger.println(F("DVP: 5"));
    // SerialDebugger.println(F("AMP: 6"));
    // SerialDebugger.println(F("EIS: 7"));
    //SerialDebugger.println(F("\tClose program: 9"));
    SerialDebugger.println();
    while(!SerialDebugger.available());
    testToRun = SerialDebugger.readString();
    running = true;
  }  // UI for sending commands via Serial
  
  switch (testToRun.toInt()) {
    case CV:
    {
      while(!ready){
        SerialDebugger.println(F("Please verify following variables values for CV test:"));
        SerialDebugger.print(F("\tdesc: "));
        SerialDebugger.println(CVdesc);
        SerialDebugger.print(F("\tgain: "));
        SerialDebugger.println(CVgain);
        SerialDebugger.print(F("\tcycles: "));
        SerialDebugger.println(CVcycles);
        SerialDebugger.print(F("\tstartV: "));
        SerialDebugger.println(CVstartV);
        SerialDebugger.print(F("\tendV: "));
        SerialDebugger.println(CVendV);
        SerialDebugger.print(F("\tvertex1: "));
        SerialDebugger.println(CVvertex1);
        SerialDebugger.print(F("\tvertex2: "));
        SerialDebugger.println(CVvertex2);
        SerialDebugger.print(F("\tstepV: "));
        SerialDebugger.println(CVstepV);
        SerialDebugger.print(F("\tfreq: "));
        SerialDebugger.println(CVfreq);
        SerialDebugger.print(F("\RFB: "));
        SerialDebugger.println(RFB);
        SerialDebugger.print(F("\tsetToZero: "));
        SerialDebugger.println(CVsetToZero);
        SerialDebugger.print(F("\tsaveData: "));
        SerialDebugger.println(CVsaveData);
        SerialDebugger.println(F("\tTo change a variable value, write variable name = new value"));
        SerialDebugger.println(F("\tSend start to run test"));
        SerialDebugger.println(F("\tSend back to return to tests list"));
        SerialDebugger.println();
        while(!SerialDebugger.available());
        String variable_to_change = SerialDebugger.readString();
        variable_to_change.trim();   
        if(variable_to_change.equals("start")){ 
          ready = true;
        }
        else if(variable_to_change.equals("back")){ 
          running = false;
          break;
        } 
        else{
          String variable = variable_to_change.substring(0,variable_to_change.indexOf('='));
          String value  = variable_to_change.substring(variable_to_change.indexOf('=')+1,variable_to_change.length());
          String test = "CV";
          variable.trim();
          value.trim();
          changeValueofVariable(test,variable,value);          
        }
      }
      if(running){
        SerialDebugger.println(F("CV test running"));
        runCV(CVgain, CVcycles, CVstartV,CVendV,CVvertex1,CVvertex2,CVstepV,CVfreq,CVsetToZero,CVsaveData);
      }      
      break;    
    }
    case SWV:
    { 
      while(!ready){
        SerialDebugger.println(F("Please verify following variables values for SWV test:"));
        SerialDebugger.print(F("\tdesc: "));
        SerialDebugger.println(SWVdesc);
        SerialDebugger.print(F("\tgain: "));
        SerialDebugger.println(SWVgain);
        SerialDebugger.print(F("\tstartV: "));
        SerialDebugger.println(SWVstartV);
        SerialDebugger.print(F("\tendV: "));
        SerialDebugger.println(SWVendV);
        SerialDebugger.print(F("\tpulseAmp: "));
        SerialDebugger.println(SWVpulseAmp);
        SerialDebugger.print(F("\tstepV: "));
        SerialDebugger.println(SWVstepV);
        SerialDebugger.print(F("\tfreq: "));
        SerialDebugger.println(SWVfreq);
        SerialDebugger.print(F("\RFB: "));
        SerialDebugger.println(RFB);
        SerialDebugger.print(F("\tsetToZero: "));
        SerialDebugger.println(SWVsetToZero);
        SerialDebugger.print(F("\tsaveData: "));
        SerialDebugger.println(SWVsaveData);
        SerialDebugger.println(F("\tTo change a variable value, write variable name = new value"));
        SerialDebugger.println(F("\tSend start to run test"));
        SerialDebugger.println(F("\tSend back to return to tests list"));
        SerialDebugger.println();
        while(!SerialDebugger.available());
        String variable_to_change = SerialDebugger.readString();
        variable_to_change.trim();   
        if(variable_to_change.equals("start")){ 
          SerialDebugger.println("ready is true");
          ready = true;
        }
        else if(variable_to_change.equals("back")){ 
          SerialDebugger.println("back is false");          
          running = false;
          break;
        } 
        else{
          String variable = variable_to_change.substring(0,variable_to_change.indexOf('='));
          String value  = variable_to_change.substring(variable_to_change.indexOf('=')+1,variable_to_change.length());
          String test = "SWV";
          variable.trim();
          value.trim();
          changeValueofVariable(test,variable,value);          
        }      
      }
      if(running){
        SerialDebugger.println(F("SWV test running"));      
        runSWV(SWVgain, SWVstartV, SWVendV, SWVpulseAmp, SWVstepV, SWVfreq, SWVsetToZero,SWVsaveData); 
      }   
      break;
    }
    case CLOSE:
    {
      //SerialDebugger.close();
    }
    default:
    {
      break;
    }
  }
}
void changeValueofVariable(String test, String variable,String value){
  if (test == "CV"){
    if(variable.equals("desc")){
      CVdesc = value;
      SerialDebugger.println("\t" + variable + " was set to " + CVdesc);
    }
    if(variable.equals("gain")){
      CVgain = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVgain);
    }
    else if(variable.equals("cycles")){
      CVcycles = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVcycles);
    }
    else if(variable.equals("startV")){
      CVstartV = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVstartV);
    }
    else if(variable.equals("endV")){
      CVendV = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVendV);
    }
    else if(variable.equals("vertex1")){
      CVvertex1 = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVvertex1);
    }
    else if(variable.equals("vertex2")){
      CVvertex2 = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVvertex2);
    }
    else if(variable.equals("stepV")){
      if (atoi(value.c_str())>=2){
        CVstepV = atoi(value.c_str());
        SerialDebugger.println("\t" + variable + " was set to " + CVstepV);
      }
      else{
        SerialDebugger.println("minimum value for step is 2");
      }
    }
    else if(variable.equals("freq")){
      CVfreq = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVfreq);
    }
    else if(variable.equals("setToZero")){
      CVsetToZero = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVsetToZero);
    }
    else if(variable.equals("saveData")){
      CVsaveData = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + CVsaveData);
    }   
  }
  if (test == "SWV"){
    if(variable.equals("desc")){
      SWVdesc = value;
      SerialDebugger.println("\t" + variable + " was set to " + SWVdesc);
    }
    if(variable.equals("gain")){
      SWVgain = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVgain);
    }
    else if(variable.equals("cycles")){
      SWVcycles = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVcycles);
    }
    else if(variable.equals("startV")){
      SWVstartV = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVstartV);
    }
    else if(variable.equals("endV")){
      SWVendV = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVendV);
    }
    else if(variable.equals("SWVpulseAmp")){
      SWVpulseAmp = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVpulseAmp);
    }
    else if(variable.equals("stepV")){
      SWVstepV = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVstepV);
    }
    else if(variable.equals("freq")){
      SWVfreq = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVfreq);
    }
    else if(variable.equals("setToZero")){
      SWVsetToZero = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVsetToZero);
    }
    else if(variable.equals("saveData")){
      SWVsaveData = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + SWVsaveData);
    }  
  } 
    if(variable.equals("RFB")){
      RFB = atoi(value.c_str());
      SerialDebugger.println("\t" + variable + " was set to " + RFB);
    }
   SerialDebugger.println();
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
      SerialDebugger.print(volts[i]);
      SerialDebugger.print(F(","));
      SerialDebugger.println(amps[i]);
    }    
  }
}
