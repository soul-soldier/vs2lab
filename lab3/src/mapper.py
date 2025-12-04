import zmq
import zlib

def main():
    context = zmq.Context()

    # 1. Input: PULL-Socket zum Empfangen  der Aufgaben (Sätze) vom Splitter
    receiver = context.socket(zmq.PULL)
    receiver.connect("tcp://localhost:5557")  # Verbindung zum Splitter

    # 2. Output: ZWEI PUSH-Sockets zu den Reducern
    # Wir brauchen zwei separate Sockets, um gezielt (und nicht zufällig) zu senden.
    sender_reducer1 = context.socket(zmq.PUSH)
    sender_reducer1.connect("tcp://localhost:5558")

    sender_reducer2 = context.socket(zmq.PUSH)
    sender_reducer2.connect("tcp://localhost:5559")

    print("Mapper gestartet. Warte auf Arbeit...")

    while True:
        # Empfange einen Satz
        sentence = receiver.recv_string()
        print(f"Empfangen: {sentence}")

        # Map-Phase: Satz in Wörter zerlegen
        words = sentence.split()

        '''
        # Sende jedes Wort an den entsprechenden Reducer
        for word in words:
            if word[0].lower() < 'm':  # Wörter, die mit A-L beginnen, gehen zu Reducer 1
                sender_reducer1.send_string(word)
                #print(f"Gesendet an Reducer 1: {word}")
            else:  # Wörter, die mit M-Z beginnen, gehen zu Reducer 2
                sender_reducer2.send_string(word)
                #print(f"Gesendet an Reducer 2: {word}")
        '''
        # Geschicktere Partitionierung der Wörter auf die beiden Reducer
        for word in words:
            # Partitionierung:
            # Wir nutzen den Hash des Wortes modulo 2.
            # Ergebnis 0 -> Reducer 1
            # Ergebnis 1 -> Reducer 2
            # Das garantiert, dass das Wort "hallo" IMMER beim gleichen Reducer landet.
            target = zlib.crc32(word.encode('utf-8')) % 2

            if target == 0:
                sender_reducer1.send_string(word)
                #print(f"Gesendet an Reducer 1: {word}")
            else:
                sender_reducer2.send_string(word)
                #print(f"Gesendet an Reducer 2: {word}")

if __name__ == "__main__":
    main()