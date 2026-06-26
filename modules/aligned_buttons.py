import streamlit as st
from .ui_components import ActionButton


class AlignedButtons:
    """Container for the three primary action buttons (Assist, Predict, Ask).

    Provides methods to render each button in a consistent layout and
    return its clicked state. This class helps keep button alignment and
    styling uniform across the application.
    """

    def __init__(self):
        self.assist = ActionButton(label="Assist", icon="💼")
        self.predict = ActionButton(label="Predict", icon="🔮")
        self.ask = ActionButton(label="Ask", icon="❓")

    def render_assist(self) -> bool:
        col1, _, _ = st.columns([1, 0.1, 0.1])
        with col1:
            return self.assist.render()

    def render_predict(self) -> bool:
        _, col2, _ = st.columns([0.1, 1, 0.1])
        with col2:
            return self.predict.render()

    def render_ask(self) -> bool:
        _, _, col3 = st.columns([0.1, 0.1, 1])
        with col3:
            return self.ask.render()
