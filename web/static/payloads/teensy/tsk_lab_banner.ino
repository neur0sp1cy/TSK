// TSK built-in | Lab Banner HID sketch (Teensy 3.2 / Keyboard)
// Compile in Arduino IDE with Teensyduino, or use the bundled .hex with teensy_loader_cli.
#include <Keyboard.h>

void setup() {
  Keyboard.begin();
  delay(2000);
  Keyboard.print("TSK | THE SKELETON KEY - lab banner\n");
  Keyboard.end();
}

void loop() {
}
