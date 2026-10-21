"""The About box — the only place the author is credited."""

from __future__ import annotations

import platform
from typing import Optional

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from mufakkira import APP_VERSION, PROJECT_URL
from mufakkira.core.i18n import tr

# Credits shown in the About box only.
AUTHOR = "م. بلال فضل (Bilal Fadl)"
AI_ASSISTANTS = (
    "Arena.ai — Agent Mode (coding assistant)",
    "DeepSeek-V4.1-Flash (early prototyping and research)",
)


def about_html() -> str:
    """Rich text for the About box.

    The direction of the text is deliberately *not* explained here: the box
    credits the people and tools behind the project and nothing else.
    """
    assistants = "<br>".join(f"• {name}" for name in AI_ASSISTANTS)
    # ``AUTHOR`` is already the exact string to show; the label lays it out
    # correctly because the Arabic run starts the line.
    arabic, latin = AUTHOR.split(" (")
    author = f"{arabic} ({latin}"
    return f"""
    <div style="line-height:150%">
      <p style="margin:0; color:#5A5A5A">{tr("about.tagline")}</p>
      <p style="margin:10px 0 0 0"><b>{tr("about.author")}:</b> {author}</p>
      <p style="margin:10px 0 0 0"><b>{tr("about.assistants")}:</b><br>{assistants}</p>
      <p style="margin:10px 0 0 0"><b>{tr("about.license")}:</b> MIT</p>
      <p style="margin:10px 0 0 0"><b>{tr("about.source")}:</b>
         <a href="{PROJECT_URL}">{PROJECT_URL}</a></p>
      <p style="margin:12px 0 0 0; color:#7A7A7A">{tr(
          "about.qt", qt=qVersion(), py=platform.python_version())}</p>
    </div>
    """


class AboutDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("action.about"))
        self.setModal(True)
        self.setMinimumWidth(520)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 20, 16)
        outer.setSpacing(14)

        # ---- header: icon, product name, one-line summary ----------------
        header = QHBoxLayout()
        header.setSpacing(14)

        icon = QLabel()
        icon.setFixedSize(64, 64)
        pixmap = QPixmap(":/icons/app.png")
        if pixmap.isNull():
            from mufakkira.core.resources import icon_pixmap

            pixmap = icon_pixmap(64)
        if not pixmap.isNull():
            icon.setPixmap(pixmap.scaled(64, 64,
                                         Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel(tr("app.name"))
        title.setObjectName("AboutTitle")
        version = QLabel(tr("about.version", version=APP_VERSION))
        version.setObjectName("AboutVersion")
        titles.addWidget(title)
        titles.addWidget(version)
        titles.addStretch(1)
        header.addLayout(titles, 1)
        outer.addLayout(header)

        # ---- credits ------------------------------------------------------
        text = QLabel(about_html())
        text.setObjectName("AboutBody")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.setOpenExternalLinks(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        text.setMinimumWidth(470)
        outer.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.ok"))
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)
