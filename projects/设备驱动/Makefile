# Simple Kbuild makefile for building driver demo modules in this directory
obj-m += char_device.o
obj-m += platform_driver.o
obj-m += interrupt_handler.o

KDIR ?= /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

