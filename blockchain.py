import hashlib
import json

from textwrap import dedent
from uuid import uuid4
from time import time
from flask import Flask, jsonify, request
from urllib.parse import urlparse

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        
        #Genesis block
        self.new_block(previous_hash=1, proof=100)
        
    def register_node(self, address):
        '''
            Add new node to list of nodes
            address: <str> address of node
            return: None
        '''
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        
    def new_block(self, proof, previous_hash=None):
        #create a new block and add to chain
        '''
            proof: <int> the proof given  by the Proof of Work algorithm
            previous_hash: (optional) <str> Hash of previous block
            return: <dict> new block
        '''
        block = {
            'index': len(self.chain) + 1,
            'timestamp' : time(),
            'transaction' : self.current_transactions,
            'proof' : proof,
            'previous_hash' : previous_hash or self.hash(self.chain[-1]),            
        }
        #reset current list of transactions
        self.current_transactions = []
        
        self.chain.append(block)
        return block
    
    def proof_of_work(self, last_proof):
        '''
            - find a number p' such that hash(pp') contains leading 4 zeros
            - p is the previous proof, and p' is the new proof
            last_proof : <int>
            return: <int>
        '''
        proof=0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
            
        return proof
    
    @staticmethod
    def valid_proof(last_proof, proof):
        '''
            Validates the proof: does hash(last_proof, proof) contain 4 leading zeros?
            last_proof: <int> previous proof
            proof: <int> current proof
            return: <bool> True if correct, False if not
        '''
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'
    
    def new_transaction(self, sender, recipient, amount):
        #adds a new transaction to the list of transactions
        '''
            sender: <str> address of the sender
            recipient: <str> address of the recipient
            amount: <int> amount
            return: <int> the index of the block that will hold this transaction
        '''
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index'] + 1
    
    def valid_chain(self, chain):
        '''
            determine if given blockchain is valid
            chain: <list> a blockchain
            return: <bool> True if valid else False
        '''
        last_block = chain[0]
        current_index = 1
        
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print('\n------\n')
            
            #check that hash of block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False
            
            #check POW
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            
            last_block = block
            current_index += 1
            
        return True
    
    def resolve_conflicts(self):
        '''
            Consensus Algorithm. Resolves conflicts by replacing our chain w/
            longest one in the network
            
            return: <bool> True if chain was replaced, False if not
        '''
        
        neighbors = self.nodes
        new_chain = None
        
        #Looking for longer chains
        max_length = len(self.chain)
        
        #verify the chains of all nodes in network
        for node in neighbors:
            response = request.get(f'http://{node}/{chain}')
        
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
            
            #check if len is longer and chain is valid
            if length > max_length and self.valid_chain(chain):
                max_length = length
                new_chain = chain
                
        #replace chain if discover a new valid longer chain
        if new_chain:
            self.chain = new_chain
            return True
        return False
    
    @staticmethod
    def hash(block):
        '''
            Create a SHA-256 hash of a block
            block: <dict> block
            return: <str>

            must ensure dictionary is ordered or else hash will be inconsistent
        '''
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    @property
    def last_block(self):
        #returns the last block in the chain
        return self.last_block[-1]
    
#Instantiate node
app = Flask(__name__)

#globally unique address 
node_identifier = str(uuid4()).replace('-', '')

#instantiate chain
blockchain = Blockchain()

#API endpoints
@app.route('/mine', methods=['GET'])
def mine():
    #run the POWA to get the next proof
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    
    #must receive a reward for finding the proof
    #sender is '0' to signify this node has mined a new coin
    blockchain.new_transaction(
        sender='0',
        recipient=node_identifier,
        amount=1,
    )
    
    #forge the new block by adding it to chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    
    response= {
        'message': 'New Block Forged',
        'index': block['index'],
        'transaction': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    
    return jsonify(response, 200)

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    
    #validate that required fields are in the POST data
    required = ['sender', 'recipient', 'amount']
    if not all(x in values for x in required):
        return 'Missing values', 400
    
    #Create new transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    
    response = {'message': f'Transaction will be added to the Block {index}'}    
    return jsonify(response, 201)

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain' : blockchain.chain,
        'length' : len(blockchain.chain),
    }
    return jsonify(response, status=200)

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    
    nodes = values.get('nodes')
    if nodes is None:
        return 'Error: Please supply a valid list of nodes', 400
    
    for node in nodes:
        blockchain.register_node(node)
    
    response = {
        'message' : 'New nodes have been added',
        'total_nodes' : list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    
    if replaced:
        response = {
            'message' : 'Current chain was replaced',
            'new_chain' : blockchain.chain,
        }
    else:
        response = {
            'message' : 'Curren chain is authoritative',
            'new_chain' : blockchain.chain,
        }
    return jsonify(response), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)