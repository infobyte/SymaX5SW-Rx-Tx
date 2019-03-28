// Syma X5SW Transmissor FINAL VERSION

#include <nRF24L01.h>
#include <printf.h>
#include <RF24.h>
#include <RF24_config.h>

//Pins CE and CSN Arduino Uno R3
#define CE_PIN 9
#define CSN_PIN 10

RF24 radio(CE_PIN, CSN_PIN);

char character;
uint8_t channel;
uint8_t packet[10];
int packet_buffer[10] = {0,0,0,0,0,0,0,0,0,0};

// Address to transmit data
uint64_t address = 0xa1ca192dbcLL;

// Channels of binding
// Alternatives: 22 , 30 , 54, 62
uint8_t chan[4] = {22, 26, 30, 34};

//// Syma checksum packets
uint8_t checksum(){

  uint8_t sum = packet[0];
  
  for (int i=1; i < 9; i++)
    sum ^= packet[i];
  
  return (sum + 0x55);
}

void setup()
{
  //Initialize serial port
  Serial.begin(2400);
  printf_begin();

  //Initialize NRF24L01 for write
  radio.begin();
  
  radio.setDataRate(RF24_250KBPS);
  radio.setCRCLength(RF24_CRC_16);
  radio.setPALevel(RF24_PA_MAX);
  radio.setAutoAck(false);
  radio.setRetries(0,0);

  radio.openWritingPipe(address);
  radio.setPayloadSize(10);
  radio.setChannel(chan[0]);
  radio.printDetails();
}

char getAndParseCommand(){
  
  character = 0x00;
  
  if (Serial.available() > 0) {
    character = Serial.read();
    Serial.print("Received: ");
    Serial.print(character);
    Serial.print("\n");
  }

  switch(character){

    case 'w':
      if(packet_buffer[0] < 127)
        packet_buffer[0] += 1;
      break;
  
    case 's':
      if(packet_buffer[0] > 0)
        packet_buffer[0] -= 1;
      break;
  
    case 'a':
      if(packet_buffer[2] > -127)
        packet_buffer[2] -= 1;
        break;
    
    case 'd':
      if(packet_buffer[2] < 127)
        packet_buffer[2] += 1;
        break;

    case 'i':
      if(packet_buffer[1] < 127)
        packet_buffer[1] += 1;
        break;

    case 'k':
      if(packet_buffer[0] > -127)
        packet_buffer[1] -= 1;
        break;

    case 'l':
      if(packet_buffer[3] < 127)
        packet_buffer[3] += 1;
        break;
    case 'j':
      if(packet_buffer[3] > -127)
        packet_buffer[3] -= 1;
        break;
  }

  return character;
}

void buildPacket(){
  /*
  Build packet bytes necessary.
  Remaining bytes not necessary modify.
  Apply OR 0x80 to numbers < 0, Highest bit is direction and remain is the value.
  */
  
  int i;
  packet[0] = packet_buffer[0];
  
  for(i = 1; i < 4; i++){
    
    if(packet_buffer[i] < 0)
      packet[i] = abs(packet_buffer[i]) | 0x80;
    else
      packet[i] = packet_buffer[i];
  }
}

void loop()
{ 
  // The drone to spin on its axis counterclockwise
  // 0f 00 7f 00 00 40 00 24 00 checksum
  // Nothing ... 00 00 00 00 00 60 00 00 01 b6  CRC 03a1

  packet[0] = 0x0f;
  packet[1] = 0x00;
  packet[2] = 0x7f;
  packet[3] = 0x00;
  packet[4] = 0x00;
  packet[5] = 0x40;
  packet[6] = 0x00;
  packet[7] = 0x24;
  packet[8] = 0x00;
  packet[9] = checksum();

  do{

    // Print data packet to send
    int i;
    Serial.print("Packet: ");
    for(i = 0; i < sizeof(packet); i++)
      Serial.print(packet[i], HEX);
    
    // Switch between three channels to transmit
    //channel += 1;
    //if(channel > 3)
    //  channel = 0;
    radio.setChannel(chan[channel]);
  
    // Send data
    bool status = radio.write(packet, sizeof(packet));
    if(status)
      Serial.println("\t OK");
    else
      Serial.println("\t FAIL");
    
    character = getAndParseCommand();
    if(character)
      buildPacket();
    
  } while (character != "q");
}

