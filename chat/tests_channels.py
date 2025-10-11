import asyncio
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator
from chat_app.asgi import application
from .models import ChatUser, ChatMessage


class ChatConsumerIntegrationTest(TransactionTestCase):
    reset_sequences = True

    def test_two_clients_receive_messages_and_message_persisted(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # create two users
        u1 = ChatUser.objects.create(name='UserA', number='100', password='x')
        u2 = ChatUser.objects.create(name='UserB', number='200', password='x')

        ids = sorted([str(u1.id), str(u2.id)])
        room_name = '_'.join(ids)
        path = f"/ws/chat/{room_name}/"

        comm1 = WebsocketCommunicator(application, path)
        comm2 = WebsocketCommunicator(application, path)

        connected1 = loop.run_until_complete(comm1.connect())
        connected2 = loop.run_until_complete(comm2.connect())
        self.assertTrue(connected1)
        self.assertTrue(connected2)

        # send a message from comm2
        msg = 'hello from userB'
        loop.run_until_complete(comm2.send_json_to({
            'message': msg,
            'sender_id': u2.id,
            'receiver_id': u1.id,
        }))

        # comm1 should receive it
        received = loop.run_until_complete(comm1.receive_json_from(timeout=2))
        self.assertEqual(received.get('message'), msg)
        self.assertEqual(int(received.get('sender_id')), u2.id)

        # message should be persisted in DB
        qs = ChatMessage.objects.filter(sender=u2, receiver=u1, content=msg)
        self.assertTrue(qs.exists())

        loop.run_until_complete(comm1.disconnect())
        loop.run_until_complete(comm2.disconnect())
