void initADC(bool fast)
{
  ADC->CTRLA.bit.ENABLE = 0; //disable the ADC while modifying
  while(ADC->STATUS.bit.SYNCBUSY == 1); //wait for synchronization
  
  //DIV32, 15-16us //below this, the ADC doesn't appear to be stable at all
  //DIV64, 20-21us
  //DIV128, 29-32us
  //DIV256, 54-55us
  //DIV512, 100us
  if(fast) ADC->CTRLB.reg = ADC_CTRLB_PRESCALER_DIV32 | ADC_CTRLB_RESSEL_12BIT;
  else ADC->CTRLB.reg = ADC_CTRLB_PRESCALER_DIV512 | ADC_CTRLB_RESSEL_12BIT;


  ADC->AVGCTRL.reg = ADC_AVGCTRL_SAMPLENUM_1 |   // 1 sample   
                      ADC_AVGCTRL_ADJRES(0x00ul); // Adjusting result by 0
  ADC->SAMPCTRL.reg = 0x00;                        // Set max Sampling Time Length to half divided ADC clock pulse (5.33us)
  ADC->CTRLA.bit.ENABLE = 1; //enable ADC
  while(ADC->STATUS.bit.SYNCBUSY == 1); // Wait for synchronization
}


//Helper method to print some data to the Serial Monitor
//after running the peak detection algorithm.
void printInfo(float m, float b, float pk, int16_t vpk)
{
  SerialDebugger.print("slope: ");
  SerialDebugger.print(m,6);
  SerialDebugger.print(", ");
  SerialDebugger.print("intercept: ");
  SerialDebugger.print(b,6);
  SerialDebugger.println();
  SerialDebugger.print("Ep: ");
  SerialDebugger.print(vpk);
  SerialDebugger.print(", ");
  SerialDebugger.print("current: ");
  SerialDebugger.print(pk,2);
  SerialDebugger.println();
}


//Initializes the LMP91000 to the appropriate settings
//for operating MiniStat.
void initLMP(uint8_t lmpGain)
{
  pStat.disableFET();
  pStat.setGain(lmpGain);
  pStat.setRLoad(0);
  pStat.setExtRefSource();
  pStat.setIntZ(1);
  pStat.setThreeLead();
  pStat.setBias(0);
  pStat.setPosBias();

  setOutputsToZero();
}


//Sets the electrochemical cell to 0V bias.
void setOutputsToZero()
{
  analogWrite(dac,0);
  pStat.setBias(0);
}


//inline float biasAndSample(int16_t voltage, uint32_t rate)
//@param        voltage: Set the bias of the electrochemical cell
//@param        rate:    How much to time should we wait to sample
//                       current after biasing the cell. This parameter
//                       sets the scan rate or the excitation frequency
//                       based on which electrochemical technique
//                       we're running.
//
//Sets the bias of the electrochemical cell then samples the resulting current.
inline float biasAndSample(int16_t voltage, uint32_t rate)
{
  SerialDebugger.print(F("Time: "));
  SerialDebugger.print(millis());
  SerialDebugger.print(F(","));

  setLMPBias(voltage);
  setVoltage(voltage);
  

  //delay sampling to set scan rate
  while(millis() - lastTime < rate);


  //output voltage of the transimpedance amplifier
  float v1 = pStat.getVoltage(analogRead(LMP), opVolt, adcBits);
  //float v2 = dacVout*.5; //the zero of the internal transimpedance amplifier
  float v2 = pStat.getVoltage(analogRead(LMP_C1), opVolt, adcBits);
  float current = 0;
  

  //the current is determined by the zero of the transimpedance amplifier
  //from the output of the transimpedance amplifier, then dividing
  //by the feedback resistor
  //current = (V_OUT - V_IN-) / RFB
  //v1 and v2 are in milliVolts
  if(LMPgain == 0) current = (((v1-v2)/1000)/RFB)*pow(10,9); //scales to nA
  else current = (((v1-v2)/1000)/TIA_GAIN[LMPgain-1])*pow(10,6); //scales to uA
  
  SerialDebugger.print(F("V1: "));
  SerialDebugger.print(v1);
  SerialDebugger.print(F(","));
  SerialDebugger.print(F("Current: "));
  SerialDebugger.print(current);
  SerialDebugger.print(F(","));

  //update timestamp for the next measurement
  lastTime = millis();
  
  return current;
}


//inline void saveVoltammogram(float voltage, float current, bool debug)
//@param        voltage: voltage or time depending on type of experiment
//                       voltage for voltammetry, time for time for
//                       time evolution experiments like chronoamperometry
//@param        current: current from the electrochemical cell
//@param        debug:   flag for determining whether or not to print to
//                       serial monitor
//
//Save voltammogram data to corresponding arrays.
inline void saveVoltammogram(float voltage, float current, bool debug)
{
  if(saveQueues && arr_cur_index < arr_samples)
  {
    volts[arr_cur_index] = (int16_t)voltage;
    amps[arr_cur_index] = current;
    arr_cur_index++;
  }

  if(debug)
  {
    SerialDebugger.print(F("Voltage: "));
    SerialDebugger.print(voltage);
    SerialDebugger.print(F(","));
    SerialDebugger.print(F("Current: "));
    SerialDebugger.print(current);
    
  }
}


inline void setVoltage(int16_t voltage)
{
  //Minimum DAC voltage that can be set
  //The LMP91000 accepts a minium value of 1.5V, adding the 
  //additional 20 mV for the sake of a bit of a buffer
  const uint16_t minDACVoltage = 1520;
  
  dacVout = minDACVoltage;
  bias_setting = 0;


  //voltage cannot be set to less than 15mV because the LMP91000
  //accepts a minium of 1.5V at its VREF pin and has 1% as its
  //lowest bias option 1.5V*1% = 15mV
  if(abs(voltage) < 15) voltage = 15*(voltage/abs(voltage));    
  
  int16_t setV = dacVout*TIA_BIAS[bias_setting];
  voltage = abs(voltage);
  
  
  while(setV > voltage*(1+v_tolerance) || setV < voltage*(1-v_tolerance))
  {
    if(bias_setting == 0) bias_setting = 1;
    
    dacVout = voltage/TIA_BIAS[bias_setting];
    
    if (dacVout > opVolt)
    {
      bias_setting++;
      dacVout = 1500;

      if(bias_setting > NUM_TIA_BIAS) bias_setting = 0;
    }
    
    setV = dacVout*TIA_BIAS[bias_setting];    
  }


  pStat.setBias(bias_setting);
  analogWrite(dac,convertDACVoutToDACVal(dacVout));
  SerialDebugger.print(F("dacVout: "));
  SerialDebugger.print(dacVout*.5);
  SerialDebugger.print(F(","));
}


//
//
//@param      voltage:    bias potential for the electrochemical cell
//@acv        acv:        amplitude of the AC signal
//
//
inline void setVoltage(int16_t voltage, int16_t acv)
{
  //Minimum DAC voltage that can be set
  //The LMP91000 accepts a minium value of 1.5V, adding the 
  //additional 20 mV for the sake of a bit of a buffer
  const uint16_t minDACVoltage = 1520;
  
  dacVout = minDACVoltage;
  bias_setting = 0;


  //voltage cannot be set to less than 15mV because the LMP91000
  //accepts a minium of 1.5V at its VREF pin and has 1% as its
  //lowest bias option 1.5V*1% = 15mV
  if(abs(voltage) < 15) voltage = 15*(voltage/abs(voltage));    


  //Variable, setV, 
  int16_t setV = dacVout*TIA_BIAS[bias_setting];
  voltage = abs(voltage);
  
  
  while( setV > voltage*(1+v_tolerance) || setV < voltage*(1-v_tolerance) )
  {
    if(bias_setting == 0) bias_setting = 1;

    
    dacVout = voltage/TIA_BIAS[bias_setting];
    
    if ( dacVout > opVolt || (voltage+acv)/TIA_BIAS[bias_setting] > opVolt )
    {
      bias_setting++;
      dacVout = minDACVoltage;

      if(bias_setting > NUM_TIA_BIAS) bias_setting = 1;
    }
    if ( (voltage-acv)/TIA_BIAS[bias_setting] < minDACVoltage )
    {
      bias_setting--;
      if(bias_setting > NUM_TIA_BIAS) bias_setting = 1;
    }
    
    setV = dacVout*TIA_BIAS[bias_setting];    
  }


  pStat.setBias(bias_setting);
  analogWrite(dac,convertDACVoutToDACVal(dacVout));
  SerialDebugger.print(dacVout*.5);
  SerialDebugger.print(F(","));
}


//inline uint16_t convertDACVoutToDACVal()
//dacVout       voltage output to set the DAC to
//
//Determines the correct value to write to the digital-to-analog
//converter (DAC) given the desired voltage, the resolution of the DAC
inline uint16_t convertDACVoutToDACVal(uint16_t dacVout)
{
  return dacVout*((float)dacResolution/opVolt);
}


//Sets the LMP91000's bias to positive or negative
inline void setLMPBias(int16_t voltage)
{
  signed char sign = (float)voltage/abs(voltage);
  
  if(sign < 0) pStat.setNegBias();
  else if (sign > 0) pStat.setPosBias();
  else {} //do nothing
}