extends Node2D
## Pixel-like light rays, independent from event simulation and JSON ownership.

var glows: Array = []


func set_objects(models: Array, sizes: Array) -> void:
	glows = []
	for index in models.size():
		if models[index].visible and models[index].glowing:
			glows.append({"position": models[index].position, "size": sizes[index]})
	queue_redraw()


func _draw() -> void:
	var color := Color(202.0 / 255, 194.0 / 255, 126.0 / 255)
	for glow in glows:
		var center: Vector2 = glow.position
		var half: Vector2 = glow.size * 0.5
		draw_rect(Rect2(center + Vector2(-half.x - 9, -1), Vector2(6, 2)), color)
		draw_rect(Rect2(center + Vector2(half.x + 3, -1), Vector2(6, 2)), color)
		draw_rect(Rect2(center + Vector2(-1, -half.y - 9), Vector2(2, 6)), color)
