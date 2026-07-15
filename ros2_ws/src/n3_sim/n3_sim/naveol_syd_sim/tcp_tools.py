import logging
from typing import TypeVar

import zmq
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)  # backported from PEP 695 (py3.12) for py3.10


class PubSubParams(BaseModel):
    host: str
    port: int


logger = logging.getLogger(__name__)


class SYDTcpInterface:
    def __init__(self, publisher_params: PubSubParams, subscriber_params: PubSubParams):
        self.publisher_params: PubSubParams = publisher_params
        self.subscriber_params: PubSubParams = subscriber_params
        self.subscriber_topic: bytes = "".encode("ascii")
        self.zmq_context: zmq.Context = zmq.Context()
        self.pub_socket: zmq.Socket | None = None
        self.sub_socket: zmq.Socket | None = None
        self.connect()

    def connect(self) -> None:
        self.connect_publisher()
        self.connect_subscriber()

    def connect_publisher(self) -> None:
        if self.pub_socket is not None:
            self.pub_socket.close()
        logger.info(f"Connecting publisher socket : {self.publisher_params}")
        try:
            self.pub_socket = self.zmq_context.socket(zmq.PUB)
            url = f"tcp://{self.publisher_params.host}:{self.publisher_params.port}"
            self.pub_socket.bind(url)
            logger.info(f"Publisher socket OK: {self.pub_socket}")
        except zmq.ZMQError:
            logger.exception(
                f"Failed to connect publisher socket: {self.publisher_params}"
            )
            self.pub_socket = None

    def connect_subscriber(self) -> None:
        if self.sub_socket is not None:
            self.sub_socket.close()
        logger.info(f"Connecting subscriber socket : {self.subscriber_params}")
        try:
            self.sub_socket = self.zmq_context.socket(zmq.SUB)
            url = f"tcp://{self.publisher_params.host}:{self.publisher_params.port}"
            self.sub_socket.connect(url)
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, self.subscriber_topic)
            logger.info(f"Subscriber socket OK: {self.sub_socket}")
        except zmq.ZMQError:
            logger.exception(
                f"Failed to connect subscriber socket: {self.subscriber_params}"
            )
            self.sub_socket = None

    def disconnect(self) -> None:
        self.disconnect_publisher()
        self.disconnect_subscriber()
        logger.info("Terminating ZMQ context")
        # this is blocking
        self.zmq_context.term()
        logger.info("ZMQ context terminated")

    def disconnect_publisher(self) -> None:
        logger.info("Closing publisher socket")
        if self.pub_socket is not None:
            self.pub_socket.close()
            self.pub_socket = None
        logger.info("Publisher socket closed")

    def disconnect_subscriber(self) -> None:
        logger.info("Closing subscriber socket")
        if self.sub_socket is not None:
            self.sub_socket.close()
            self.sub_socket = None
        logger.info("Subscriber socket closed")

    def send(self, command: BaseModel) -> None:
        if self.pub_socket is None:
            return
        try:
            payload = command.model_dump_json().encode("ascii")
            self.pub_socket.send(payload)
        except zmq.ZMQError:
            logger.exception("Failed to send command on publisher socket")

    def receive(self, model_class: type[T]) -> T | None:
        if self.sub_socket is None:
            return None
        try:
            raw = self.sub_socket.recv(zmq.NOBLOCK)
        except zmq.Again:
            return None
        except zmq.ZMQError:
            logger.exception("Failed to receive data on subscriber socket")
            return None
        try:
            return model_class.model_validate_json(raw)
        except ValueError:
            logger.exception(f"Failed to parse received data: {raw!r}")
            return None
