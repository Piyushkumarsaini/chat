import websocket, threading, time, json


def run_client(name, send_message=None):
    ws = websocket.create_connection('ws://127.0.0.1:8001/ws/chat/1_2/')
    def recv():
        try:
            while True:
                data = ws.recv()
                print(f"{name} recv:", data)
        except Exception as e:
            print(name, 'recv error', e)
    t = threading.Thread(target=recv, daemon=True)
    t.start()
    if send_message:
        time.sleep(0.5)
        ws.send(json.dumps(send_message))
        print(name, 'sent')
    time.sleep(1)
    ws.close()

if __name__ == '__main__':
    t1 = threading.Thread(target=run_client, args=('client1', None))
    t2 = threading.Thread(target=run_client, args=('client2', {'message':'hello from client2','sender_id':2,'receiver_id':1}))
    t1.start(); t2.start()
    t1.join(); t2.join()
