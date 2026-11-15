print("Initializing TripPlanner AI & connecting to database... Please wait.")

from backend import run_travel_agent

user_input = input("\nEnter travel request: ")

print("\nRunning travel agent pipeline (fetching flights, hotels, and planning itinerary)...")
response = run_travel_agent(
    user_input=user_input,
    thread_id="test_user"
)

print("\nFINAL RESPONSE:\n")
print(response["answer"])