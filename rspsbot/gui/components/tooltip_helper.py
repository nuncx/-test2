"""
Tooltip helper for RSPS Color Bot v3
"""
import logging
from PyQt5.QtWidgets import QWidget, QToolTip, QLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Get module logger
logger = logging.getLogger('rspsbot.gui.components.tooltip_helper')

class TooltipHelper:
    """
    Enhanced helper class for adding tooltips to widgets
    """
    
    @staticmethod
    def set_tooltip_font(font_size=10):
        """
        Set the font for all tooltips
        
        Args:
            font_size: Font size
        """
        font = QFont()
        font.setPointSize(font_size)
        QToolTip.setFont(font)
    
    @staticmethod
    def add_tooltip(widget, text, rich_text=True):
        """
        Add a tooltip to a widget
        
        Args:
            widget: Widget to add tooltip to
            text: Tooltip text
            rich_text: Whether to use rich text formatting
        """
        if rich_text:
            widget.setToolTip(f"<div style='font-size: 10pt;'>{text}</div>")
        else:
            widget.setToolTip(text)
    
    @staticmethod
    def add_tooltips(widgets_and_texts):
        """
        Add tooltips to multiple widgets
        
        Args:
            widgets_and_texts: List of (widget, text) tuples
        """
        for widget, text in widgets_and_texts:
            TooltipHelper.add_tooltip(widget, text)
    
    @staticmethod
    def add_tooltip_to_layout_items(layout, tooltips_dict):
        """
        Add tooltips to all widgets in a layout
        
        Args:
            layout: QLayout object
            tooltips_dict: Dictionary mapping widget names to tooltip texts
        """
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                widget = item.widget()
                if widget.objectName() in tooltips_dict:
                    TooltipHelper.add_tooltip(widget, tooltips_dict[widget.objectName()])
            elif item.layout():
                TooltipHelper.add_tooltip_to_layout_items(item.layout(), tooltips_dict)
    
    @staticmethod
    def create_tooltip(title, description):
        """
        Create a rich text tooltip with title and description
        
        Args:
            title: Tooltip title
            description: Tooltip description
            
        Returns:
            str: Formatted tooltip HTML
        """
        return f"""
        <div style='font-size: 10pt;'>
            <b>{title}</b>
            <p>{description}</p>
        </div>
        """