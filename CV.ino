////CYCLIC VOLTAMMETRY
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



//void runCV()
//
//@param      lmpGain:    gain setting for LMP91000
//@param      cycles:     number of times to run the scan
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      vertex1:    edge of the scan
//                        If vertex1 is greater than starting voltage, we start
//                        the experiment by running CV in the forward
//                        (oxidation) direction.
//@param      vertex2:    edge of the scan
//                        If vertex2 is greater than starting voltage, we start
//                        the experiment by running CV in the reverse
//                        (reduction) direction.
//@param      stepV:      how much to increment the voltage by
//@param      freq:       scanning frequency
//                        in the case of CV, the frequency will be changed to ms
//@param      setToZero:  Boolean determining whether the bias potential of
//                        the electrochemical cell should be set to 0 at the
//                        end of the experiment.
//
//Runs the electrochemical technique, Cyclic Voltammetry. In this
//technique the electrochemical cell is biased at a series of
//voltages and the current at each subsequent voltage is measured.
void runCV(uint8_t lmpGain, uint8_t cycles, int16_t startV,
        int16_t endV, int16_t vertex1, int16_t vertex2,
        int16_t stepV, uint16_t rate, bool setToZero,bool saveData)
{
  //for amptamer with good step resolution
  float slope = 0;
  float intercept = 0;
  float peak = 0;
  int16_t v_peak = 0;
  //sets LMPGain to CVgain here so it stays a general var
  LMPgain = lmpGain;
  SerialDebugger.println(CVdesc);
  SerialDebugger.println(F("Time(ms),Zero,LMP,V1,Time(ms),Zero,LMP,V1,Voltage,Current"));

  initLMP(lmpGain);
  //the method automatically handles if stepV needs to be positive or negative
  //no need for the user to specify one or the other
  //this step deals with that in case the user doesn't know
  stepV = abs(stepV);
  //figures out the delay needed to achieve a given scan rate
  //delay is dependent on desired rate and number of steps taken
  //more steps = smaller delay since we'll need to go by a bit faster
  //to sample at more steps vs. less steps, but at the same rate
  rate = (1000.0*stepV)/rate;  

  //Reset Arrays
  for(uint16_t i = 0; i < arr_samples; i++) volts[i] = 0;
  for(uint16_t i = 0; i < arr_samples; i++) amps[i] = 0;


  lastTime = millis();
  
  for (int i = 0; i < cycles;i++){
    runCVForward(cycles, startV, endV, vertex1, vertex2, stepV, rate,saveData);
    printVoltsAndCurrent();
    runCVBackward(cycles, startV, endV, vertex1, vertex2, stepV, rate,saveData);
    printVoltsAndCurrent();
  }

  analyst.calcBaseline(vertex1,vertex2,MB_APTAMER_BASE, amps, volts, slope, intercept, arr_samples);
  analyst.getPeakCurrent(vertex1,vertex2,MB_APTAMER_PEAK, amps, volts, slope, intercept,peak,v_peak,arr_samples);
  printInfo(slope, intercept, peak, v_peak);

  //sets the bias of the electrochemical cell to 0V
  if(setToZero) setOutputsToZero();
  arr_cur_index = 0;
}


//@param      cycles:     number of times to run the scan
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      vertex1:    edge of the scan
//                        If vertex1 is greater than starting voltage, we start
//                        the experiment by running CV in the forward
//                        (oxidation) direction.
//@param      vertex2:    edge of the scan
//                        If vertex2 is greater than starting voltage, we start
//                        the experiment by running CV in the reverse
//                        (reduction) direction.
//@param      stepV:      how much to increment the voltage by
//@param      rate:       scanning rate
//                        in the case of CV, scanning rate is in mV/s
//Runs CV in the forward (oxidation) direction first
void runCVForward(uint8_t cycles, int16_t startV, int16_t endV,
                  int16_t vertex1, int16_t vertex2, int16_t stepV, uint16_t rate,bool saveData)
{
  int16_t j = startV;
  float i_cv = 0;
  
  for(uint8_t i = 0; i < cycles; i++)
  {
    if(i==cycles-3) saveQueues = true;
    else saveQueues = false;
    
    //j starts at startV
    for (j; j <= vertex1; j += stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j -= 2*stepV; //increment j twice to avoid biasing at the vertex twice
  
  
    //j starts right below the first vertex
    for (j; j >= vertex2; j -= stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j += 2*stepV; //increment j twice to avoid biasing at the vertex twice
  
  
    //j starts right above the second vertex
    for (j; j <= endV; j += stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j -= 2*stepV; //increment j twice to avoid biasing at the vertex twice
    
  }
}


//@param      cycles:     number of times to run the scan
//@param      startV:     voltage to start the scan
//@param      endV:       voltage to stop the scan
//@param      vertex1:    edge of the scan
//                        If vertex1 is greater than starting voltage, we start
//                        the experiment by running CV in the forward
//                        (oxidation) direction.
//@param      vertex2:    edge of the scan
//                        If vertex2 is greater than starting voltage, we start
//                        the experiment by running CV in the reverse
//                        (reduction) direction.
//@param      stepV:      how much to increment the voltage by
//@param      rate:       scanning rate
//                        in the case of CV, scanning rate is in mV/s
//Runs CV in the reverse (reduction) direction first
void runCVBackward(uint8_t cycles, int16_t startV, int16_t endV,
                   int16_t vertex1, int16_t vertex2, int16_t stepV, uint16_t rate,bool saveData)
{  
  int16_t j = startV;
  float i_cv = 0;
  
  for(uint8_t i = 0; i < cycles; i++)
  {
    if(i==cycles-2) saveQueues = true;
    else saveQueues = false;
    
    //j starts at startV
    for (j; j >= vertex1; j -= stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j += 2*stepV; //increment j twice to avoid biasing at the vertex twice
    

    //j starts right above vertex1
    for (j; j <= vertex2; j += stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j -= 2*stepV; //increment j twice to avoid biasing at the vertex twice
  

    //j starts right below vertex2
    for (j; j >= endV; j -= stepV)
    {
      i_cv = biasAndSample(j,rate);
      SerialDebugger.print(i+1);
      SerialDebugger.print(F(","));
      saveVoltammogram(j, i_cv, saveData);
      SerialDebugger.println();
    }
    j += 2*stepV; //increment j twice to avoid biasing at the vertex twice
    
  }
}
