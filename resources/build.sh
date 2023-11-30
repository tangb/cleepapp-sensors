#!/bin/bash
apt install wiringpi
gcc -o ../scripts/dht22 dht22.c -lwiringPi

