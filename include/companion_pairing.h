#pragma once
namespace companion_pairing {
void begin();
void poll();
bool configured();
const char* host();
const char* key();
const char* controlToken();
}
