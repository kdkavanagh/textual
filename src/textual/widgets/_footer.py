from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import rich.repr
from rich.text import Text

from ..app import ComposeResult
from ..binding import Binding
from ..containers import ScrollableContainer
from ..reactive import reactive
from ..widget import Widget

if TYPE_CHECKING:
    from ..screen import Screen


@rich.repr.auto
class FooterKey(Widget):
    COMPONENT_CLASSES = {
        "footer-key--key",
        "footer-key--description",
    }

    DEFAULT_CSS = """
    FooterKey {
        width: auto;
        height: 1;
        background: $panel;
        color: $text-muted;
        .footer-key--key {
            color: $secondary;
            background: $panel;
            text-style: bold;
            padding: 0 1;
        }

        .footer-key--description {
            padding: 0 1 0 0;
        }

        &:light .footer-key--key {
            color: $primary;
        }

        &:hover {
            background: $panel-darken-2;
            color: $text;
            .footer-key--key {
                background: $panel-darken-2;
            }
        }

        &.-disabled {
            text-style: dim;
            background: $panel;
            &:hover {
                .footer-key--key {
                    background: $panel;
                }
            }
        }

        &.-compact {
            .footer-key--key {
                padding: 0;
            }
            .footer-key--description {
                padding: 0 0 0 1;
            }
        }
    }
    """

    upper_case_keys = reactive(False)
    ctrl_to_caret = reactive(True)
    compact = reactive(True)

    def __init__(
        self,
        key: str,
        key_display: str,
        description: str,
        action: str,
        disabled: bool = False,
        tooltip: str = "",
        classes="",
    ) -> None:
        self.key = key
        self.key_display = key_display
        self.description = description
        self.action = action
        self._disabled = disabled
        if disabled:
            classes += " -disabled"
        super().__init__(classes=classes)
        if tooltip:
            self.tooltip = tooltip

    def render(self) -> Text:
        key_style = self.get_component_rich_style("footer-key--key")
        description_style = self.get_component_rich_style("footer-key--description")
        key_display = self.key_display
        key_padding = self.get_component_styles("footer-key--key").padding
        description_padding = self.get_component_styles(
            "footer-key--description"
        ).padding
        if self.upper_case_keys:
            key_display = key_display.upper()
        if self.ctrl_to_caret and key_display.lower().startswith("ctrl+"):
            key_display = "^" + key_display.split("+", 1)[1]
        description = self.description
        label_text = Text.assemble(
            (
                " " * key_padding.left + key_display + " " * key_padding.right,
                key_style,
            ),
            (
                " " * description_padding.left
                + description
                + " " * description_padding.right,
                description_style,
            ),
        )
        label_text.stylize_before(self.rich_style)
        return label_text

    async def on_mouse_down(self) -> None:
        if self._disabled:
            self.app.bell()
        else:
            self.app.simulate_key(self.key)

    def _watch_compact(self, compact: bool) -> None:
        self.set_class(compact, "-compact")


@rich.repr.auto
class Footer(ScrollableContainer, can_focus=False, can_focus_children=False):
    DEFAULT_CSS = """
    Footer {
        layout: grid;
        grid-columns: auto;
        background: $panel;
        color: $text;
        dock: bottom;
        height: 1;
        scrollbar-size: 0 0;
        &.-compact {
            grid-gutter: 1;
        }
        FooterKey.-command-palette  {
            dock: right;
                        
            padding-right: 1;
            border-left: vkey $foreground 20%;                
        }
    }
    """

    upper_case_keys = reactive(False)
    """Upper case key display."""
    ctrl_to_caret = reactive(True)
    """Convert 'ctrl+' prefix to '^'."""
    compact = reactive(False)
    """Display in compact style."""
    _bindings_ready = reactive(False, repaint=False)
    """True if the bindings are ready to be displayed."""
    show_command_palette = reactive(True)
    """Show the key to invoke the command palette."""

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        upper_case_keys: bool = False,
        ctrl_to_caret: bool = True,
        show_command_palette: bool = True,
    ) -> None:
        """A footer to show key bindings.

        Args:
            *children: Child widgets.
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes for the widget.
            disabled: Whether the widget is disabled or not.
            upper_case_keys: Show the keys in upper case.
            ctrl_to_caret: Show `ctrl+` as `^`.
            show_command_palette: Show key binding to command palette, on the right of the footer.
        """
        super().__init__(
            *children,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.set_reactive(Footer.upper_case_keys, upper_case_keys)
        self.set_reactive(Footer.ctrl_to_caret, ctrl_to_caret)
        self.set_reactive(Footer.show_command_palette, show_command_palette)

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return
        bindings = [
            (binding, enabled, tooltip)
            for (_, binding, enabled, tooltip) in self.screen.active_bindings.values()
            if binding.show
        ]
        action_to_bindings: defaultdict[str, list[tuple[Binding, bool, str]]]
        action_to_bindings = defaultdict(list)
        for binding, enabled, tooltip in bindings:
            action_to_bindings[binding.action].append((binding, enabled, tooltip))

        self.styles.grid_size_columns = len(action_to_bindings)
        for multi_bindings in action_to_bindings.values():
            binding, enabled, tooltip = multi_bindings[0]
            yield FooterKey(
                binding.key,
                binding.key_display or self.app.get_key_display(binding.key),
                binding.description,
                binding.action,
                disabled=not enabled,
                tooltip=tooltip,
            ).data_bind(
                Footer.upper_case_keys,
                Footer.ctrl_to_caret,
                Footer.compact,
            )
        if self.show_command_palette and self.app.ENABLE_COMMAND_PALETTE:
            for key, binding in self.app._bindings:
                if binding.action in (
                    "app.command_palette",
                    "command_palette",
                ):
                    yield FooterKey(
                        key,
                        binding.key_display or binding.key,
                        binding.description,
                        binding.action,
                        classes="-command-palette",
                        tooltip=binding.tooltip or binding.description,
                    )
                    break

    def on_mount(self) -> None:
        async def bindings_changed(screen: Screen) -> None:
            self._bindings_ready = True
            if self.is_attached and screen is self.screen:
                await self.recompose()

        self.screen.bindings_updated_signal.subscribe(self, bindings_changed)

    def on_unmount(self) -> None:
        self.screen.bindings_updated_signal.unsubscribe(self)

    def watch_compact(self, compact: bool) -> None:
        self.set_class(compact, "-compact")
