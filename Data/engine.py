import yaml
from transitions.extensions import HierarchicalMachine

# 1. Load your flexible configuration
with open("workflow.yaml", "r") as f:
    config = yaml.safe_load(f)

# 2. Flatten your configuration states into 'stage.status' formats
states = []
for stage in config['stages']:
    for status in stage['statuses']:
        states.append(f"{stage['name']}_{status}")

# 3. Define the core object that Python/AI/Humans manipulate
class TaskObject(object):
    def __init__(self, name):
        self.name = name

    def on_enter_review_pending_human(self):
        print(f"🤖 AI completed check. [Notification]: Task '{self.name}' is now waiting for Human Approval!")

# 4. Initialize a lightweight state machine
task = TaskObject("Personal Data Pipeline Project")
machine = HierarchicalMachine(model=task, states=states, initial='ingestion_raw')

# 5. Dynamically map transitions from config
for t in config['transitions']:
    machine.add_transition(
        trigger=t['trigger'],
        source=t['source'].replace('.', '_'),
        dest=t['dest'].replace('.', '_')
    )

# --- Simulation of your Polling Loop Engine ---
print(f"Current State: {task.state}") # Out: ingestion_raw

# Python Actor works
task.process_data()
task.complete_processing()
print(f"Current State: {task.state}") # Out: ingestion_processing -> ingestion_completed

# Hand off to Review Stage
task.send_to_review()                  # Out: review_pending_ai

# AI Agent evaluates and triggers next step
task.ai_approve()                      # Triggers the on_enter callback note

# Human Agent logs in later, approves, moving it to deployment stage
task.human_approve()
print(f"Final State: {task.state}")   # Out: deployment_queued
