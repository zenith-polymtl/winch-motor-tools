# winch-motor-tools

Useful motor commands:
Start: 91 00 00 00 00 00 00 00
Stop: 92 00 00 00 00 00 00 00

Turn at 2 RPM: 94 00 00 A0 C1 D0 07 00

Position Control at 0 in 5 seconds: 95 00 00 00 00 32 14 00

Read zero position (gear): 84 00 14 00 00 00 00 00

Modify zero position (gear): 83 00 14 00 ...

Read position (gear): B4 13 00 00 00 00 00 00

Read Iq: B4 09 00 00 00 00 00 00

Get fault: B2 00 00 00 00 00 00 00