from uuid import uuid4

import can

from busscope.socketcan_transmission import SocketCanTransmitter
from busscope.transmission import ManualTransmission


class ReadyInterface:
    def ensure_ready(self, channel: str) -> None:
        del channel


def test_transmitter_sends_exactly_one_frame_through_virtual_bus() -> None:
    channel = f"tx-{uuid4().hex[:8]}"
    receiver = can.Bus(interface="virtual", channel=channel, receive_own_messages=False)

    def open_sender(requested_channel: str) -> can.BusABC:
        return can.Bus(
            interface="virtual",
            channel=requested_channel,
            receive_own_messages=False,
        )

    transmitter = SocketCanTransmitter(ReadyInterface(), open_sender)
    request = ManualTransmission(
        channel=channel,
        arbitration_id=0x1ABCDE,
        payload=bytes.fromhex("01 02 03 04 05 06 07 08"),
    )

    try:
        transmitter.send(request)
        received = receiver.recv(timeout=0.2)

        assert received is not None
        assert received.arbitration_id == request.arbitration_id
        assert bytes(received.data) == request.payload
        assert received.is_extended_id is True
        assert receiver.recv(timeout=0.05) is None
    finally:
        receiver.shutdown()
