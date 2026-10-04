extends Node2D
## Small alpha-blended squares, below foreground ghosts and UI; no input/RNG.

var field: RefCounted


func _init(model: RefCounted) -> void:
	field = model


func _draw() -> void:
	var rgb: Array = field.settings.color
	for particle in field.particles:
		var radius := int(particle.radius)
		var point := Vector2(int(particle.position.x) - radius, int(particle.position.y) - radius)
		draw_rect(Rect2(point, Vector2.ONE * radius * 2), Color8(rgb[0], rgb[1], rgb[2], particle.alpha))
