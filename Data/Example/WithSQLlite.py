import sqlite3
from transitions import Machine

# 1. Setup SQLite Database
conn = sqlite3.connect('state_machine.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY,
        name TEXT,
        state TEXT
    )
''')
conn.commit()

# 2. Define your PyTransitions Model
class Entity:
    states = ['asleep', 'awake', 'running']
    
    def __init__(self, name, initial_state='asleep'):
        self.name = name
        self.state = initial_state
        
        # Initialize state machine
        self.machine = Machine(
            model=self, 
            states=self.states, 
            initial=initial_state,
            after_state_change='save_to_db' # Auto-trigger DB save
        )
        
        # Define transitions
        self.machine.add_transition(trigger='wake_up', source='asleep', dest='awake')
        self.machine.add_transition(trigger='start_running', source='awake', dest='running')
        self.machine.add_transition(trigger='sleep', source='*', dest='asleep')

    def save_to_db(self):
        """Callback to update the database after every state change"""
        # Note: You should save or generate an ID in a real application
        entity_id = 1 
        cursor.execute('''
            INSERT OR REPLACE INTO entities (id, name, state)
            VALUES (?, ?, ?)
        ''', (entity_id, self.name, self.state))
        conn.commit()
        print(f"[{self.name}] transitioned to '{self.state}' and saved to DB.")

# 3. Usage
my_robot = Entity(name="BotAlpha")

# Triggers state changes and automatically runs save_to_db()
my_robot.wake_up()
my_robot.start_running()
my_robot.sleep()

# Close connection when done
conn.close()
