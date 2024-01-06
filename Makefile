# macOS or if you dont have a GPU
start-xtts-server:
	@echo "Running xtts server"
	python -m xtts_api_server

# deepspeed uses GPU - for windows/linux 
start-xtts-server-ds:
	@echo "Running xtts server with deepspeed"
	python -m xtts_api_server --deepspeed

# not working because of spaces, just use the python command
tts:
	@echo "Running quickTTS"
	python quickTTS.py $(text) --voice=$(voice) --language=$(language) --am=$(am)
