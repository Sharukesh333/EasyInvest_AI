import streamlit as st


class ActionButton:
    """Reusable Streamlit button with consistent styling.

    Parameters
    ----------
    label: str
        Text to display on the button.
    key: str | None, optional
        Unique Streamlit key for the widget. If ``None`` a key is generated
        from the label.
    icon: str, optional
        Emoji or icon prefix to prepend to the label.
    button_type: str, optional
        Streamlit button ``type`` argument (e.g., "primary", "secondary").
    full_width: bool, optional
        Whether to use ``use_container_width=True`` for a full‑width button.
    """

    def __init__(
        self,
        label: str,
        key: str | None = None,
        icon: str = "",
        button_type: str = "primary",
        full_width: bool = True,
    ):
        self.label = label
        self.key = key or f"btn_{label.lower().replace(' ', '_')}"
        self.icon = icon
        self.type = button_type
        self.full_width = full_width

    def render(self) -> bool:
        """Render the button and return its clicked state.

        Returns
        -------
        bool
            ``True`` if the button was clicked in the current Streamlit run.
        """
    def render(self) -> bool:
        """Render the button and return its clicked state.

        Returns
        -------
        bool
            ``True`` if the button was clicked in the current Streamlit run.
        """
        # Construct the display label with optional icon
        display_label = f"{self.icon} {self.label}" if self.icon else self.label
        # Render the Streamlit button with consistent styling
        return st.button(
            label=display_label,
            key=self.key,
            type=self.type,
            use_container_width=self.full_width,
        )
