import sys
import os
from DVA import *
from PyQt5 import QtWidgets



def display_menu():
    print("*" * 40)
    print("* {:^36} *".format("Welcome to the Distance Vector Algorithm"))
    print("*" * 40)
    print("* {:<36} *".format("1. Display Initial Distance Vector Table for Each Node (Highly Recommended)"))
    print("* {:<36} *".format("2. Run Algorithm In Single Step Mode"))
    print("* {:<36} *".format("3. Run Algorithm Without Intervention"))
    print("* {:<36} *".format("4. Adjust Link Cost"))
    print("* {:<36} *".format("5. Exit"))
    print("*" * 40)
                                                                                                                                                                                       
def adjust_and_run_algorithm(graph, window):
    sourceid, destid, link_cost = input("Enter SourceID DestinationID Cost: \nExample Format: 1 2 3\nEnter Yours: ").split()

    status = DVAlgoLinkChange(graph, sourceid, destid, link_cost)
    if status != 'Not Exist':

        print("\nHow would you like to run the DV algorithm?")
        print("1. Single Step Mode")
        print("2. Without Intervention")
        first_choice = input("Enter your choice: ")

        if first_choice == "1":
            DVAlgorithmBreaks(graph, window)
        
        elif first_choice == "2":
            DVAlgorithmNoBreaks(graph, window)

        else:
            print("Invalid choice. Returning to main menu.")


def handle_menu_choice(choice, graph, initWindow, window):

    if choice == "1":
        printInitDVtable(graph, initWindow)
        return True
        
    elif choice == "2":
        DVAlgorithmBreaks(graph, window)
        shutdownAllServers(graph)
        
    elif choice == "3":
        DVAlgorithmNoBreaks(graph, window)
        shutdownAllServers(graph)

    elif choice == "4":
        adjust_and_run_algorithm(graph, window)

    elif choice == "5":
        shutdownAllServers(graph)
        sys.exit()
    
    return False

def main():
    # Initialize GUI window
    app = QtWidgets.QApplication(sys.argv)
    initWindow = MyGUI()
    window = MyGUI()


    filename = input("Enter filename: ")
    if not os.path.isfile(filename):
        print("File not found.")
        sys.exit()

    graph = parse_input(filename)
    initDVtable(graph)
    startServers(graph)

    keep_running = True
    while keep_running:
        display_menu()
        choice = input("Enter your choice: ")
        keep_running = handle_menu_choice(choice, graph, initWindow, window)

    input("Press Enter to exit...")
    shutdownAllServers(graph)
    sys.exit()


if __name__ == "__main__":
    main()
