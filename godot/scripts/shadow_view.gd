extends Sprite2D
## A reusable pixel shadow on the floor, independent of sprite rotation and AI.


func _init(display_size: Vector2 = Vector2(64, 64)) -> void:
	var width := maxi(1, int(display_size.x * 0.58))
	var height := maxi(5, int(display_size.y * 0.08))
	var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
	image.fill(Color.TRANSPARENT)
	# Fill rather than overlap translucent draw calls, matching the source pixels.
	image.fill_rect(Rect2i(floori(width / 6.0), 0, floori(width * 4 / 6.0), height), Color8(0, 0, 5, 46))
	image.fill_rect(Rect2i(0, floori(height / 3.0), width, maxi(2, floori(height / 3.0))), Color8(0, 0, 5, 34))
	texture = ImageTexture.create_from_image(image)
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	centered = false
	offset = Vector2(-width * 0.5, 0)


func follow(base_position: Vector2, half_height: float) -> void:
	# GhostModel.position already includes the moving loop, but not hover bobbing.
	position = base_position + Vector2(0, half_height + 19)
