from twitchio.ext import commands
from gemini_prompt import *
import creds
from pyboy import PyBoy, WindowEvent
import queue
import threading
import traceback
import os
import asyncio
import creds

import google.generativeai as genai

genai.configure(api_key=creds.GOOGLE_API_KEY)

model = genai.GenerativeModel('gemini-pro')

MOVES = {
    "UP": (WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP), 
    "DOWN": (WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN),
    "LEFT": (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT), 
    "RIGHT": (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT), 
    "START": (WindowEvent.PRESS_BUTTON_START, WindowEvent.RELEASE_BUTTON_START),
    "A": (WindowEvent.PRESS_BUTTON_A, WindowEvent.RELEASE_BUTTON_A),
    "B": (WindowEvent.PRESS_BUTTON_B, WindowEvent.RELEASE_BUTTON_B),
}
ram_map = {
    '0xD163': 'Current HP of the player’s Pokémon in a battle',
    '0xD164': 'Max HP of the player’s Pokémon in a battle',
    '0xD16B': 'Level of the player’s Pokémon in a battle',
    '0xD16D': 'Attack of the player’s Pokémon in a battle',
    '0xD16F': 'Defense of the player’s Pokémon in a battle',
    '0xD171': 'Speed of the player’s Pokémon in a battle',
    '0xD173': 'Special of the player’s Pokémon in a battle',
    '0xD500': 'Start of the map tiles data',
    '0xD6A3': 'End of the map tiles data',
    '0xC100': 'Start of the sprites data',
    '0xC1FF': 'End of the sprites data',
    '0xD355': 'Badges of the player',
    '0xD36E': 'Player’s current location map ID',
    '0xD36F': 'Player’s current location bank ID',
    '0xD163-D3C0': 'Player\'s Pokémon Data',
    '0xCFE5-D0B7': 'Enemy Pokémon Data',
    '0xD31D-D347': 'Player\'s Item Data',
    '0xD057': 'Enemy\'s Trainer ID',
    '0xD0F5': 'Battle Type',
    '0xD35E': 'Current Map ID',
    '0xD347-D349': 'Player\'s Money',
    '0xD356': 'Player\'s Badges',
    '0xD158-D162': 'Player\'s Name',
    '0xD163': 'Player\'s Pokémon Count',
    'CC24': 'Y position of the menu cursor',
    'CC25': 'X position of the menu cursor',
    'CC26': 'Currently selected menu item',
    #'CC27': 'Tile hidden by the menu cursor',
    #'CC28': 'ID of the last menu item',
    #'CC2A': 'ID of the previously selected menu item',
    #'CC2B': 'Last position of the cursor on the party/Bill\'s PC screen',
    #'CC2C': 'Last position of the cursor on the item screen',
    'CC2D': 'Last position of the cursor on the START/battle menu',
    'CC2F': 'Index (in party) of the Pokémon currently sent out',
    #'CC30-CC31': 'Pointer to cursor tile in C3A0 buffer',
    'CC36': 'ID of the first displayed menu item',
    'CC35': 'Item highlighted with Select',
    'C3A0-C507': 'Buffer of all tiles onscreen',
    #'C508-C5CF': 'Copy of previous tile buffer',
    'C100-C1FF': 'Data for all sprites on the current map (part 1)',
    'C200-C2FF': 'Data for all sprites on the current map (part 2)',
    #'C300-C39F': 'OAM DMA buffer'
}

state_description = 'Pokemon Red Game State:\n'
agent_instructions = "Based on:\n1. A game state from Pyboy \n2. A batch of messages from a chat. \nPlease provide: \n1. MOVES: A sequence of 10 gameboy buttons to press (separated by single spaces with no other characters) that must be in the set {UP, DOWN, LEFT, RIGHT, A, B, START} based on the game state and the messages\n2. MESSAGE: A single, clever reply to the batch of messages with no quotes."

def parse_response(response):
    split_response = response.split('\n')
    moves = split_response[0].split(': ')[1].split()
    message = split_response[1].split(': ')[1]
    return moves, message

def get_memory_range(pyboy, start, end):
    return [pyboy.get_memory_value(i) for i in range(start, end+1)]


def describe_game_state(pyboy):
    global state_description

    state_description = 'Pokemon Red Game State:\n'
    for addr, desc in ram_map.items():
        if '-' in addr:  # Range of addresses
            # start, end = [int(a, 16) for a in addr.split('-')]
            # values = get_memory_range(pyboy, start, end)
            pass
        else:  # Single address
            values = [pyboy.get_memory_value(int(addr, 16))]

        state_description += f'{desc}: {values}\n'
    
    # # Fetch sprite data
    # sprite_data_1 = get_memory_range(pyboy, 0xC100, 0xC1FF)
    # sprite_data_2 = get_memory_range(pyboy, 0xC200, 0xC2FF)
    # state_description += f'Sprite data (part 1): {sprite_data_1}\n'
    # state_description += f'Sprite data (part 2): {sprite_data_2}\n'

    # # Fetch tile data
    # tile_data = get_memory_range(pyboy, 0xD500, 0xD6A3)
    # state_description += f'Tile data: {tile_data}\n'

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()
    
def gemini_completion(game_chat_info):

    model_input = agent_instructions + "\n" + game_chat_info + "\nrecall your output should be in the following format - even if it is a random set of moves and a random message" 
    print(model_input)
    response = model.generate_content(model_input)

    moves_and_reply = response.text.strip()
    print(moves_and_reply)
    return moves_and_reply

class Bot(commands.Bot):

    conversation = list()
    move_queue = queue.Queue()
    message_batch = list()

    def __init__(self):
        super().__init__(token= creds.TWITCH_TOKEN, prefix='!', initial_channels=[creds.TWITCH_CHANNEL])

    def run_pyboy(self):
        game_file_path = os.path.join('C:', os.sep, 'Users', 'brett', 'Documents', 'gemini-vtuber', 'pokemon_red.gb')

        with PyBoy(game_file_path) as pyboy:
            describe_game_state(pyboy)

            while not pyboy.tick():
                try:
                    if not self.move_queue.empty():
                        move_press, move_release = self.move_queue.get()
                        print(f"Received move: {move_press}, {move_release}")
                        pyboy.send_input(move_press)
                        pyboy.tick() 
                        pyboy.send_input(move_release)
                        pyboy.tick()
                        #move describe game outside of condition will lead to game state for gemini to be very recent 
                        describe_game_state(pyboy)
                except Exception as e:
                    print(f"Error making move: {e}")
                    traceback.print_exc()

    async def send_message(self, message):
        await self.get_channel(creds.TWITCH_CHANNEL).send(message)

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        threading.Thread(target=self.run_pyboy, name="run_pyboy", args=(), daemon=True).start()
        while True:  # Infinite loop to process chat and send to gemini every n seconds
            if len(self.message_batch) > 0:
                combined_input = f"Game State:\n{state_description}\nMessages:\n" + "\n".join(self.message_batch)
                response = gemini_completion(combined_input)  # Add gemini completion function here
                moves, text = parse_response(response)

                # Queue moves
                for move in moves:
                    if move in MOVES.keys() and self.move_queue.qsize() < 10:  # Throttle move input
                        self.move_queue.put(MOVES[move])


                if text:
                    await self.send_message(text)

                self.message_batch = []
            await asyncio.sleep(4)  # Wait for 4 seconds before next gemini call

"""     async def event_message(self, message):
        print(f'Message from {message.author.name}: {message.content}')
        if len(self.message_batch) < 5:
            self.message_batch.append(message.content) """

    

bot = Bot()
bot.run()