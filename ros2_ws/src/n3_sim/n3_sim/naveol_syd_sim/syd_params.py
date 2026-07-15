from __future__ import annotations

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node

from n3_sim.naveol_syd_sim.syd_model import SydCommandFrame, SydStatusFrame
from n3_sim.naveol_syd_sim.tcp_tools import PubSubParams, SYDTcpInterface


class SydModel(BaseModel):
    pub_host: str = Field(
        default="127.0.0.1", description="Host for the ZMQ publisher socket."
    )
    pub_port: int = Field(
        default=43000, description="Port for the ZMQ publisher socket."
    )
    sub_host: str = Field(
        default="127.0.0.1", description="Host for the ZMQ subscriber socket."
    )
    sub_port: int = Field(
        default=41000, description="Port for the ZMQ subscriber socket."
    )
    poll_rate_hz: float = Field(
        default=20.0, ge=1.0, le=100.0, description="Polling rate in Hz."
    )


class SydParams(PydanticParamsBase[SydModel]):
    model_class = SydModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)


class SydInterface:
    def __init__(self, params: SydParams):
        p = params.p
        self.tcp = SYDTcpInterface(
            publisher_params=PubSubParams(
                host=p.pub_host,
                port=p.pub_port,
            ),
            subscriber_params=PubSubParams(
                host=p.sub_host,
                port=p.sub_port,
            ),
        )

    def write(self, command: SydCommandFrame) -> None:
        self.tcp.send(command)

    def read(self) -> SydStatusFrame | None:
        return self.tcp.receive(SydStatusFrame)

    def disconnect(self) -> None:
        self.tcp.disconnect()
