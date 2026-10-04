extends Node2D
## One readable speech bubble, independent of the model and conversation timing.

const FONT_SIZE := 18
const MAX_TEXT_WIDTH := 250.0
var font := SystemFont.new()
var style := StyleBoxFlat.new()
var message: String = ""
var lines: Array[String] = []
var extent := Vector2(70, 40)


func _init() -> void:
	font.font_names = PackedStringArray(["Yu Gothic", "Meiryo", "Noto Sans CJK JP"])
	style.bg_color = Color(0.90, 0.91, 0.88)
	style.set_corner_radius_all(5)
	visible = false


func set_message(text: String) -> void:
	if text == message:
		return
	message = text
	visible = not message.is_empty()
	lines.clear()
	var line := ""
	var width := 50.0
	for character in message:
		if not line.is_empty() and font.get_string_size(line + character, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x > MAX_TEXT_WIDTH:
			lines.append(line)
			width = maxf(width, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x)
			line = ""
		line += character
	if not line.is_empty():
		lines.append(line)
		width = maxf(width, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x)
	extent = Vector2(width + 20, maxf(38, lines.size() * font.get_height(FONT_SIZE) + 16))
	queue_redraw()


func _draw() -> void:
	draw_style_box(style, Rect2(Vector2.ZERO, extent))
	for index in lines.size():
		draw_string(font, Vector2(10, 8 + font.get_ascent(FONT_SIZE) + index * font.get_height(FONT_SIZE)), lines[index], HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, Color(0.10, 0.11, 0.14))
