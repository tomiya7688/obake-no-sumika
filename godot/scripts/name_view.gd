extends Node2D
## Pointer-only label. It never consumes input or changes the simulation.

const FONT_SIZE := 16
var font := SystemFont.new()
var style := StyleBoxFlat.new()
var displayed_name: String = ""
var extent := Vector2.ZERO


func _init() -> void:
	font.font_names = PackedStringArray(["Yu Gothic", "Meiryo", "Noto Sans CJK JP"])
	style.bg_color = Color8(17, 20, 29)
	style.border_color = Color8(105, 111, 120)
	style.set_border_width_all(1)
	visible = false


func set_label(text: String) -> void:
	if displayed_name == text:
		return
	displayed_name = text
	visible = not text.is_empty()
	extent = Vector2(font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x + 12, font.get_height(FONT_SIZE) + 6)
	queue_redraw()


func place_below(rendered_bounds: Rect2, screen: Rect2) -> void:
	position = Vector2(
		clampf(rendered_bounds.get_center().x - extent.x * 0.5, screen.position.x, screen.end.x - extent.x),
		clampf(rendered_bounds.end.y + 6, screen.position.y, screen.end.y - extent.y)
	)


func _draw() -> void:
	draw_style_box(style, Rect2(Vector2.ZERO, extent))
	draw_string(font, Vector2(6, 3 + font.get_ascent(FONT_SIZE)), displayed_name, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, Color8(235, 236, 229))
