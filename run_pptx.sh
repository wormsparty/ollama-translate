#!/bin/sh

if ! which ollama; then
	curl -fsSL https://ollama.com/install.sh | sh
fi

ollama pull mistral-small3.2

if [ ! -d .venv ]; then
	python3 -m venv .venv
	. .venv/bin/activate
	pip3 install -r requirements.txt
else
	. .venv/bin/activate
fi

python3 translate_pptx.py
