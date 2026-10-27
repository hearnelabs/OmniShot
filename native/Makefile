CC ?= gcc
CFLAGS ?= -O3 -fPIC -Wall -Wextra -march=x86-64-v3 -shared
TARGET = ../omnishot/core/libomnishot_stitch.so

all: $(TARGET)

$(TARGET): stitcher.c
	$(CC) $(CFLAGS) stitcher.c -o $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean
