/*
 * DHT22 for Raspberry Pi with WiringPi
 * Author: Hyun Wook Choi
 * Modified by Tang for Cleep
 * Version: 0.1.0
 * https://github.com/ccoong7/DHT22
 */


#include <stdio.h>
#include <string.h>
#include <wiringPi.h>

unsigned short data[5] = {0, 0, 0, 0, 0};

static const char NO_DATA[] = "NO_DATA";
static const char GPIO_INIT_FAILED[] = "GPIO_INIT_FAILED";
static const char NO_ERROR[] = "";
static const char INVALID_GPIO[] = "INVALID_GPIO";

static const unsigned char MAX_RETRIES = 3; // 5 * 2 = 10 seconds of max script duration
static const unsigned int WATCHDOG_THRESHOLD = 50000;

short readData(unsigned short signal)
{
    unsigned short val = 0x00;
    unsigned short signal_length = 0;
    unsigned short val_counter = 0;
    unsigned short loop_counter = 0;

    for (int watchdog=0; watchdog<=WATCHDOG_THRESHOLD; watchdog++)
    {
        // Count only HIGH signal
        while (digitalRead(signal) == HIGH)
        {
            signal_length++;
            
            // When sending data ends, high signal occur infinite.
            // So we have to end this infinite loop.
            if (signal_length >= 200)
            {
                return -1;
            }

            delayMicroseconds(1);
        }

        // If signal is HIGH
        if (signal_length > 0)
        {
            loop_counter++;    // HIGH signal counting

            // The DHT22 sends a lot of unstable signals.
            // So extended the counting range.
            if (signal_length < 10)
            {
                // Unstable signal
                val <<= 1;        // 0 bit. Just shift left
            }

            else if (signal_length < 30)
            {
                // 26~28us means 0 bit
                val <<= 1;        // 0 bit. Just shift left
            }

            else if (signal_length < 85)
            {
                // 70us means 1 bit    
                // Shift left and input 0x01 using OR operator
                val <<= 1;
                val |= 1;
            }

            else
            {
                // Unstable signal
                return -1;
            }

            signal_length = 0;    // Initialize signal length for next signal
            val_counter++;        // Count for 8 bit data
        }

        // The first and second signal is DHT22's start signal.
        // So ignore these data.
        if (loop_counter < 3)
        {
            val = 0x00;
            val_counter = 0;
        }

        // If 8 bit data input complete
        if (val_counter >= 8)
        {
            // 8 bit data input to the data array
            data[(loop_counter / 8) - 1] = val;

            val = 0x00;
            val_counter = 0;
        }
    }

    return -1;
}

void toJson(float celsius, float humidity, const char* error) {
    printf("{\"celsius\": %0.2f, \"humidity\": %0.2f, \"error\": \"%s\"}\n", celsius, humidity, error);
}

void usage() {
    printf("Usage: ./dht22 <pin>\n");
    printf(" - pin  : raspberry pi physical pin number where sensor is connected to.\n");
}

int main(int argc, char* argv[])
{
    float humidity;
    float celsius;
    // float fahrenheit;
    short checksum;
    unsigned short signal;
    unsigned char valid = 0;

    // parameters
    if ( argc!=2 ) { 
        usage();
        return 1;
    }

    // get pin number
    sscanf(argv[1], "%d", &signal);

    // GPIO Initialization
    if (wiringPiSetupPhys() == -1)
    {
        // printf("[x_x] GPIO Initialization FAILED.\n");
        toJson(0.0, 0.0, GPIO_INIT_FAILED);
        return -126;
    }

    for (unsigned char i = 0; i < MAX_RETRIES; i++)
    {
        pinMode(signal, OUTPUT);

        // Send out start signal
        digitalWrite(signal, LOW);
        delay(20);                    // Stay LOW for 5~30 milliseconds
        pinMode(signal, INPUT);        // 'INPUT' equals 'HIGH' level. And signal read mode

        readData(signal);        // Read DHT22 signal

        // The sum is maybe over 8 bit like this: '0001 0101 1010'.
        // Remove the '9 bit' data using AND operator.
        checksum = (data[0] + data[1] + data[2] + data[3]) & 0xFF;
        
        // If Check-sum data is correct (NOT 0x00), display humidity and temperature
        if (data[4] == checksum && checksum != 0x00)
        {
            // * 256 is the same thing '<< 8' (shift).
            humidity = ((data[0] * 256) + data[1]) / 10.0;
            celsius = data[3] / 10.0;

            // If 'data[2]' data like 1000 0000, It means minus temperature
            if (data[2] == 0x80)
            {
                celsius *= -1;
            }

            // do not compute farenheit
            // fahrenheit = ((celsius * 9) / 5) + 32;

            // Display all data
            // printf("TEMP: %6.2f *C (%6.2f *F) | HUMI: %6.2f %\n\n", celsius, fahrenheit, humidity);
            toJson(celsius, humidity, NO_ERROR);

            // valid data received, stop here
            valid = 1;
            break;
        }
        else
        {
            // printf("[x_x] Invalid Data. Try again.\n\n");
        }

        // Initialize data array for next loop
        for (unsigned char i = 0; i < 5; i++)
        {
            data[i] = 0;
        }

        delay(2000);    // DHT22 average sensing period is 2 seconds
    }
            
    if (!valid) {
        toJson(0.0, 0.0, NO_DATA);
    }

    return 0;
}
