 ////SQUARE WAVE VOLTAMMETRY
 ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//void runSWV()
//
//@param      lmpGain:    gain setting for LMP91000
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      pulseAmp:   amplitude of square wave
//@param      stepV:      how much to increment the voltage by
//@param      freq:       square wave frequency
//@param      setToZero:  Boolean determining whether the bias potential of
//                        the electrochemical cell should be set to 0 at the
//                        end of the experiment.
//
//Runs the electrochemical technique, Square Wave Voltammetry. In this
//technique the electrochemical cell is biased at a series of
//voltages with a superimposed squar wave on top of the bias voltage.
//The current is sampled on the forward and the reverse pulse.
//https://www.basinc.com/manuals/EC_epsilon/Techniques/Pulse/pulse#square
//
void runSWV(uint8_t lmpGain, int16_t startV, int16_t endV,
            int16_t pulseAmp, int16_t stepV, double freq, bool setToZero,bool saveData)
{

float slope = 0;
float intercept = 0;
float peak = 0;
int16_t v_peak = 0;
//sets LMPGain to SWVgain here so it stays a general var
 LMPgain = lmpGain;
SerialDebugger.println(SWVdesc);
SerialDebugger.println(F("Time(ms),Zero,LMP,V1,Time(ms),Zero,LMP,V1,Voltage,Current"));

initLMP(lmpGain);
pulseAmp = abs(pulseAmp);
uint16_t ms = (uint16_t)(1000.0 / (freq)); //converts frequency to milliseconds

//testing shows that time is usually off by 1 ms or so, therefore
//we subtract 1 ms from the calculated rate to compensate
ms -= 1;

saveQueues = true;

//Reset Arrays
for(uint16_t i = 0; i < arr_samples; i++) volts[i] = 0;
for(uint16_t i = 0; i < arr_samples; i++) amps[i] = 0;

 if (startV < endV || stepV < 0){
      runSWVForward(startV, endV, pulseAmp, stepV, ms,saveData);  
    }
    else if (startV > endV || stepV > 0){
      runSWVForward(startV, endV, pulseAmp, stepV, ms,saveData);  
    }
    else if (startV < endV || stepV > 0){
      runSWVBackward(startV, endV, pulseAmp, stepV, ms,saveData);  
    }
    else if (startV > endV || stepV < 0){
      runSWVBackward(startV, endV, pulseAmp, stepV, ms,saveData);  
    }
    else{
      SerialDebugger.print("Error in input");
    }

printVoltsAndCurrent();

analyst.calcBaseline(MB_APTAMER_BASE, amps, volts, slope, intercept, arr_samples);
analyst.getPeakCurrent(MB_APTAMER_PEAK, amps, volts, slope, intercept, peak, v_peak, arr_samples);
printInfo(slope, intercept, peak, v_peak);

arr_cur_index = 0;
if(setToZero) setOutputsToZero();

}


//void runSWVForward
//
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      pulseAmp:   amplitude of square wave
//@param      stepV:      how much to increment the voltage by
//@param      freq:       square wave frequency
//@param      saveData:   prints Voltamogramme values to serial monitor

//Runs SWV in the forward (oxidation) direction. The bias potential is
//swept from a more negative voltage to a more positive voltage.
void runSWVForward(int16_t startV, int16_t endV, int16_t pulseAmp,
                   int16_t stepV, double freq,bool saveData)
{
  float i_forward = 0;
  float i_backward = 0;

  for (int16_t j = startV; j <= endV; j += stepV)
  {
    //positive pulse
    i_forward = biasAndSample(j + pulseAmp,freq);

    //negative pulse
    i_backward = biasAndSample(j - pulseAmp,freq);
    

    saveVoltammogram(j, i_forward-i_backward, saveData);
    SerialDebugger.println();
  }
}


//void runSWVBackward
//
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      pulseAmp:   amplitude of square wave
//@param      stepV:      how much to increment the voltage by
//@param      freq:       square wave frequency
//@param      saveData:   prints Voltamogramme values to serial monitor
//
//Runs SWV in the backward (reduction) direction. The bias potential
//is swept from a more positivie voltage to a more negative voltage.
void runSWVBackward(int16_t startV, int16_t endV, int16_t pulseAmp,
                    int16_t stepV, double freq,bool saveData)
{
  float i_forward = 0;
  float i_backward = 0;
  
  for (int16_t j = startV; j >= endV; j -= stepV)
  {
    //positive pulse
    i_forward = biasAndSample(j + pulseAmp,freq);
    
    //negative pulse
    i_backward = biasAndSample(j - pulseAmp,freq);

    saveVoltammogram(j, i_forward-i_backward, saveData);
    SerialDebugger.println();
  }
}
