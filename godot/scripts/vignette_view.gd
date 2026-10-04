extends Sprite2D
## Static rounded border mask, drawn over the background but below the world.


static func integer_between(value: Variant, minimum: int, maximum: int) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and value >= minimum and value <= maximum


static func validate(settings: Variant, room_size: Vector2i) -> String:
	if not settings is Dictionary:
		return "background.vignette must be an object"
	var color: Variant = settings.get("color")
	if not color is Array or color.size() != 3:
		return "background.vignette.color must contain three integer channels"
	for channel in color:
		if not integer_between(channel, 0, 255):
			return "background.vignette.color channels must be between 0 and 255"
	var ranges := {
		"max_inset": [0, floori(room_size.x / 2.0)], "step": [1, room_size.x],
		"border_width": [1, 100], "radius": [0, 500], "alpha_start": [0, 255],
		"alpha_divisor": [1, 1000], "min_alpha": [0, 255]
	}
	for field in ranges:
		if not integer_between(settings.get(field), ranges[field][0], ranges[field][1]):
			return "Invalid background.vignette." + field
	return ""


static func rounded_span(rect: Rect2i, radius: int, y: int) -> Vector2i:
	# Half-open scanline bounds using pixel centers; clamp large corner radii.
	if not rect.has_area() or y < rect.position.y or y >= rect.end.y:
		return Vector2i.ZERO
	var clamped := mini(radius, floori(mini(rect.size.x, rect.size.y) / 2.0))
	var edge := 0
	var distance := minf(y - rect.position.y + 0.5, rect.end.y - y - 0.5)
	if distance < clamped:
		var vertical := clamped - distance
		edge = ceili(clamped - sqrt(clamped * clamped - vertical * vertical) - 0.5)
	return Vector2i(rect.position.x + edge, rect.end.x - edge)


static func render_mask(settings: Dictionary, room_size: Vector2i) -> Image:
	var image := Image.create(room_size.x, room_size.y, false, Image.FORMAT_RGBA8)
	image.fill(Color.TRANSPARENT)
	var width := int(settings.border_width)
	for inset in range(0, int(settings.max_inset), int(settings.step)):
		var rect := Rect2i(inset, floori(inset / 2.0), room_size.x - inset * 2, room_size.y - inset)
		var radius := mini(int(settings.radius), floori(mini(rect.size.x, rect.size.y) / 2.0))
		var inner := rect.grow(-width)
		var alpha := maxi(int(settings.min_alpha), int(settings.alpha_start) - floori(float(inset) / settings.alpha_divisor))
		var color := Color8(settings.color[0], settings.color[1], settings.color[2], alpha)
		for y in range(rect.position.y, rect.end.y):
			var outer := rounded_span(rect, radius, y)
			var hole := rounded_span(inner, maxi(0, radius - width), y)
			if hole == Vector2i.ZERO:
				image.fill_rect(Rect2i(outer.x, y, outer.y - outer.x, 1), color)
			else:
				image.fill_rect(Rect2i(outer.x, y, hole.x - outer.x, 1), color)
				image.fill_rect(Rect2i(hole.y, y, outer.y - hole.y, 1), color)
	# Later rings overwrite alpha instead of blending repeatedly, as in pygame.
	return image


func _init(settings: Dictionary, room_size: Vector2i) -> void:
	texture = ImageTexture.create_from_image(render_mask(settings, room_size))
	centered = false
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
