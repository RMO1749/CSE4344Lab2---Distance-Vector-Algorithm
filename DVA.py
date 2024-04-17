import numpy as np
import socket
import threading
import json
from PyQt5 import QtWidgets
from GUI import Ui_MainWindow
from PyQt5.QtGui import QStandardItem
import time
import os

class Node:
    """
    Network node with capabilities to manage connections (edges) to other nodes
    Handles its own server for communication
    Maintain's distance vector tables for routing.
    Each node uses a unique server port and uses 'localhost' as the hostname.

    Attributes:
        name: The name of the node, typically a number like 1-5.
        serverPort: The unique port number for the server operations of this node.
        hostname: The network address of the node, default is 'localhost'.
        edges: A list of Edge instances representing connections to other nodes.
        initTable: A list of lists representing the initial distance vector table.
        updatedInit: Stores distance vector tables received from other nodes.
        shutdown: A flag to signal whether the server should be shut down.
        serverThread: The thread running this node's server process.
    """
    def __init__(self, name, serverPort, hostname='localhost'):
        self.name = name
        self.edges = []
        self.initTable = []
        self.shutdown = False
        self.serverPort = serverPort
        self.hostname = hostname
        self.updatedInit = []
        self.serverThread = None

    def addEdge(self, destination, cost):
        """Creates an edge to another node with specified cost."""
        self.edges.append(Edge(self, destination, cost))

    def signalShutdown(self):
        """Signals the server to shut down by setting the shutdown flag."""
        self.shutdown = True

    def serverSide(self, ready_event):
        """Operates the server side accepting connections and handling incoming data."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.hostname, self.serverPort))
        server_socket.settimeout(1.0)
        server_socket.listen()
        ready_event.set()

        try:
            while not self.shutdown:
                try:
                    connection, address = server_socket.accept()
                    data = connection.recv(1024).decode('utf-8')
                    data = json.loads(data)
                    self.updatedInit.append(data)
                    response = "Data received"
                    connection.sendall(response.encode('utf-8'))
                    connection.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error: {e}")
                    continue
        finally:
            server_socket.close()
            print(f"Server {self.name} has shut down.")

    def clientSide(self, message, portNumber):
        """Sends a message to another node's server."""
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.hostname, portNumber))
        client_socket.sendall(message.encode('utf-8'))
        client_socket.close()

    def startServer(self, ready_event):
        """Starts the server process for this node in a separate thread."""
        self.serverThread = threading.Thread(target=self.serverSide, args=(ready_event,))
        self.serverThread.start()

class Edge:
    """
    Represents an edge in a network graph with a weight (cost).

    Attributes:
        source (Node): The source node of the edge.
        destination (Node): The destination node of the edge.
        weight (float): The cost associated with the edge.
    """
    def __init__(self, source, destination, weight):
        self.source = source
        self.destination = destination
        self.weight = weight

def parse_input(filename):
    """
    Parses an input file
    Constructs a graph represented as a dictionary of Node objects.
    Assigns a unique server port to each node starting from 10 and increments this port number for each new node to ensure
    unique server communication channels.

    Returns:
        dict: A dictionary where keys are node names and values are Node objects fully initialized with
              connections to other nodes.
              
    """
    graph = {}
    portNumber = 10  # Initial port number for the first node

    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.strip() == "End of Input":
                    break  # Stop processing if 'End of Input' is found
                words = line.strip().split()
                if len(words) == 3:
                    source_name, dest_name, weight = words
                    weight = float(weight)
                    
                    # Increment port numbers
                    if source_name not in graph:
                        graph[source_name] = Node(source_name, portNumber)
                        portNumber += 5
                    if dest_name not in graph:
                        graph[dest_name] = Node(dest_name, portNumber)
                        portNumber += 10
                    
                    # Add bidirectional edges to the graph
                    graph[source_name].addEdge(graph[dest_name], weight)
                    graph[dest_name].addEdge(graph[source_name], weight)

    except IOError as e:
        print(f"Could not read file: {filename}. Error: {e}")
        raise

    return graph


def calculate_cost(graph, source_node_name, dest_node_name):
    if source_node_name == dest_node_name:
        return 0 #no cost to reach itself
    if source_node_name in graph:
        for edge in graph[source_node_name].edges:
            if edge.destination.name == dest_node_name:
                return edge.weight
    return np.inf # return infinity if no direct connection exists. 

    
def initDVtable(graph):
    """
    Initializes the distance vector table for each node in the graph.
    Calculates the cost from each node to every other node in the graph using the calculate_cost function.
    Each node's initTable attribute stores the resulting table. 
    The table includes distances to all other nodes. 
    Uses direct connection costs where available and infinity where no direct connection exists.

    Example:
       The initTable for '1' would look like: [['1', '1', 0], ['1', '2', 7], ['1', '3', inf]]
    """
    keys = list(graph.keys())
    for index, values in enumerate(keys):
        if index < len(keys):
            source_node = values
            for dest_node in keys:
                cost = calculate_cost(graph, source_node, dest_node)
                graph[values].initTable.append([source_node, dest_node, cost]) 


def sendDVtoNeighbor(graph):
    """
    Sends the current distance vector tables from each node to all its neighboring nodes.
    Iterates over each node and uses the client-side communication to send the
    node's distance vector table to each of its neighbors except itself. 
    Only sends data when a direct connection exists.(neither infinity nor zero)

    Note:
        The clientSide function of each node is used to send its distance vector table in JSON format.
    """
    keys = list(graph.keys())
    for source_node in keys:
        for dest_node in keys:
            if source_node == dest_node: #ignore if source_node == dest_node
                continue
            cost = calculate_cost(graph, source_node, dest_node)
            if cost != np.inf and cost != 0:
                message = graph[source_node].initTable
                str_message = json.dumps(message) #convert a list to json format 
                graph[source_node].clientSide(str_message, graph[dest_node].serverPort)

def shutdownAllServers(graph):
    for node in graph.values():
        node.signalShutdown()

    for node in graph.values():
        if node.serverThread is not None:
            node.serverThread.join()

def startServers(graph):
    ready_events = [threading.Event() for _ in graph]
    for node, event in zip(graph.values(), ready_events):
        node.startServer(event)
    
    for event in ready_events:
        event.wait()

    print("All servers are ready. ")

def updateDV(graph, node_id):
    """
    Updates the distance vector table for a specific node based on newly received data.

    Returns:
        tuple: The updated distance vector table and a boolean indicating if changes were made.

    Initializes 'changed' to False to track if updates occur.
    Gets the current distance vector table from the graph for the given node.
    Converts the list of lists into a dictionary for easier access.
    Loops through each received distance vector table.
    Checks and updates the node's distance vector if a shorter path through a neighbor is found.
    Converts the updated dictionary back into the list format.
    Updates the node's table in the graph with the new values.

    """
    changed = False 
    own_dv_table = graph[node_id].initTable
    own_dv_dict = {dst: cost for _, dst, cost in own_dv_table} 

    received_tables = graph[node_id].updatedInit

    for received_table in received_tables:
        for src, dst, received_cost in received_table: 
            
            if src != node_id:
                if src in own_dv_dict:

                    src_to_dst_cost = own_dv_dict[src] + received_cost
                    if dst not in own_dv_dict or src_to_dst_cost < own_dv_dict[dst]:
                        print(f"Node {node_id} Changes")
                        print(f" Changed from {own_dv_dict[dst]} to {src_to_dst_cost} ")
                        own_dv_dict[dst] = src_to_dst_cost
                        changed = True

    updated_own_dv_table = [[node_id, dst, cost] for dst, cost in own_dv_dict.items()]
    graph[node_id].initTable = updated_own_dv_table

    return updated_own_dv_table, changed



def DVAlgorithmBreaks(graph, mainWindowInstance):
    """
    Runs the Distance Vector algorithm in single-step mode
    Allows for user input at each cycle to decide whether to proceed or stop.

    Repeats sending distance vectors and updating until no changes are detected or max cycles are reached(base condition to prevent infinite looping).
    Updates GUI with changed distance vectors.
    Asks the user to continue or halt the algorithm after each update.
    """
    cycles = 0
    stable = False #Assume stable until proven otherwise
    max_cycles = len(graph) * 50 #chosen at random as a base condition

    while not stable and cycles < max_cycles:
        stable = True
        cycles += 1
        sendDVtoNeighbor(graph)  # Send DV tables to all neighbors
        for node in graph:
            updated_table, changed = updateDV(graph, node)
            if changed:
                print(f"Node {node} updated table: {updated_table}")
                stable = False  # If any updates, not stable
                mainWindowInstance.updateRoutingTableForNode(graph, node, updated_table)
                mainWindowInstance.show()

        if stable:
            break

        decision = input("Continue to next cycle? (Y/N): ")
        if decision.upper() != 'Y':
            print("User halted the algorithm.")
            input("Press Enter to Exit...")
            try:
                os._exit(1)
            except Exception as e:
                    print(f"Error when exiting: {e}")

        if cycles >= max_cycles:
            print("Reached maxiumum cycles without becoming stable")
            break

    print(f"Algorithm has reached a stable state. It achieved this in {cycles} cycles")

def DVAlgorithmNoBreaks(graph, mainWindowInstance):
    """
    Same as DVAlgorithmWithBreaks
    Except no user intervention
    
    """
    stable = False
    cycles = 0
    max_cycles = len(graph) * 50 #chosen at random as a base condition
    start_time = time.time()
    while not stable:
        stable = True 
        cycles += 1
        sendDVtoNeighbor(graph) 
        for node in graph:
            updated_table, changed = updateDV(graph, node)
            if changed:
                print(f"Node {node} updated table: {updated_table}")
                stable = False 
                mainWindowInstance.updateRoutingTableForNode(graph, node, updated_table)
                mainWindowInstance.show()

        if stable:
            break

        if cycles >= max_cycles:
            print("Reached maxiumum cycles without becoming stable")
            break

    end_time = time.time()
    total_time = end_time - start_time
    total_time = round(total_time, 3) 
   
    print(f"Algorithm has reached a stable state, It did so in {cycles} cycles")
    print(f"Total time taken: {total_time} seconds.")


def DVAlgoLinkChange(graph, sourceid, destid, link_cost):
    """
    Adjusts the cost of the link between two specified nodes in the graph.

    Verifies both nodes exist in the graph.
    Updates the link cost in the initial tables of both nodes if found.
    Prints the adjusted costs and updates the tables accordingly.

    """
    link_cost = float(link_cost) 

    if sourceid in graph and destid in graph:
        print("Before Adjustment: \n ")
        print(graph[sourceid].initTable)
        print(graph[destid].initTable)
        found = False

        for i, (src, dest, cst) in enumerate( graph[sourceid].initTable):
            if src == sourceid and dest == destid:
                graph[sourceid].initTable[i] = [src, dest, link_cost]
                found = True
                break
            
            if not found:
                print("Link not found")
         #birectional graphs, so changes reflect in both nodes    
        for i, (src, dest, cst) in enumerate( graph[destid].initTable):
            if src == destid and dest == sourceid:
                graph[destid].initTable[i] = [src, dest, link_cost]
                found = True
                break
            
            if not found:
                print("Link not found")

        print(f"Link cost between {sourceid} and {destid} adjusted to {link_cost}.")
        print(f"Link cost between {destid} and {sourceid} adjusted to {link_cost}.")
        print("After Adjustment: \n ")
        print(graph[sourceid].initTable)
        print(graph[destid].initTable)
    else:
        print("One or both of the specified nodes do not exist.")
        return 'Not Exist'

def getNodeOrder(graph, node_id):
    """
    Retrieves the position order of a node within the graph dictionary keys.
    returns: The 1-based index of the node within the graph keys. Returns None if the node does not exist.
    Used for connecting node to their order in the GUI models.
    """
    try:
        return list(graph.keys()).index(node_id) + 1  # + 1 to match our starting position
    except ValueError:
        return None

def printInitDVtable(graph, initWindow):
    initWindow.printInitDVtableFn(graph)
    initWindow.show()

class MyGUI(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None, node =None):
        super(MyGUI, self).__init__(parent)
        self.setupUi(self)
        self.node = node

    '''
        function that will only print the initial distance vector for each node
    '''
    def printInitDVtableFn(self, graph):
        for node_id in graph:
            routing_table = graph[node_id].initTable

            node_order = getNodeOrder(graph, node_id)
            if node_order is None:
                print(f"No model found for node {node_id}")
                return
            
            model_key = f'model{node_order}'   
            model = self.models.get(model_key)

            if not model:
                print(f"No model found for node order {node_order}")
                return
            model.clear()
            model.setHorizontalHeaderLabels(["Source Node", "Destination Node", "Cost"])

            for row in routing_table:
                items = [QStandardItem(str(cell)) for cell in row]
                model.appendRow(items)

    '''
    function will print all updated tables 
    '''
    def updateRoutingTableForNode(self, graph, node_id, routing_table):
     
        node_order = getNodeOrder(graph, node_id)
        if node_order is None:
            print(f"No model found for node {node_id}")
            return
        
        model_key = f'model{node_order}'   
        model = self.models.get(model_key)

        if not model:
            print(f"No model found for node order {node_order}")
            return
        model.clear()
        model.setHorizontalHeaderLabels(["Source Node", "Destination Node", "Cost"])

        for row in routing_table:
            items = [QStandardItem(str(cell)) for cell in row]
            model.appendRow(items)

        

        
 

 