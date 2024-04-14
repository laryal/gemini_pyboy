# gemini_pyboy
Get Google's Gemini Pro to play Pokemon with the Gemini API, Twitch and PyBoy
# Getting Started
pip install -q -U google-generativeai
pip install pyboy==1.5.6
pip install twitchio==2.9.1

Clone this repository and add in your own credentials in creds.py (websites to obtain tokens/keys in creds.py)

When you have created an Access Token for your Twitch channel and a Gemini project with the Google Cloud Console (and obtained an API key) you can start to get the chat bot to play Pokemon or any other Pyboy-compatible ROM (just need a GB file which I am not including here). 

Run gameboy_agent_gemini.py and then type a message in the chat on your Twitch channel. Gemini should reply with a set of moves (goes to PyBoy) and a message in the Twitch chat! 

Try to make your own Gemini Plays Pokemon!
