.PHONY: test

all: test

test:
	py.test . -s -v
