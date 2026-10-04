extends RefCounted
## Ambient simulation only. Its RNG never belongs to either ghost or the deck.

var settings: Dictionary
var particles: Array[Dictionary] = []
var rng := RandomNumberGenerator.new()
var elapsed: float = 0.0


static func number_between(value: Variant, minimum: float, maximum: float) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and value >= minimum and value <= maximum


static func integer_between(value: Variant, minimum: int, maximum: int) -> bool:
	return number_between(value, minimum, maximum) and float(value) == floorf(float(value))


static func increasing_range(value: Variant, nonnegative: bool = false) -> bool:
	return value is Array and value.size() == 2 and number_between(value[0], 0 if nonnegative else -10000, 10000) and number_between(value[1], -10000, 10000) and value[0] < value[1]


static func validate(definition: Variant, room_height: int) -> String:
	if not definition is Dictionary:
		return "motes must be an object"
	if not integer_between(definition.get("count"), 0, 1000):
		return "Invalid motes.count"
	for field in ["x_range", "y_range", "reset_y_range", "speed_range"]:
		if not increasing_range(definition.get(field), field == "speed_range"):
			return "Invalid motes." + field
	if not number_between(definition.get("top"), 0, room_height):
		return "Invalid motes.top"
	for field in ["drift_speed", "drift_amount"]:
		if not number_between(definition.get(field), 0, 100):
			return "Invalid motes." + field
	var radii: Variant = definition.get("radii")
	if not radii is Array or radii.is_empty():
		return "motes.radii must be a non-empty array"
	for radius in radii:
		if not integer_between(radius, 1, 100):
			return "Invalid motes.radii"
	var alpha: Variant = definition.get("alpha_range")
	if not alpha is Array or alpha.size() != 2 or not integer_between(alpha[0], 0, 255) or not integer_between(alpha[1], 0, 255) or alpha[0] > alpha[1]:
		return "Invalid motes.alpha_range"
	var color: Variant = definition.get("color")
	if not color is Array or color.size() != 3:
		return "motes.color must contain three integer channels"
	for channel in color:
		if not integer_between(channel, 0, 255):
			return "Invalid motes.color"
	return ""


func _init(definition: Dictionary, base_seed: int) -> void:
	settings = definition.duplicate(true)
	var seed_value := base_seed & 0x7fffffff
	for character in "scenery/motes":
		seed_value = (seed_value * 31 + character.unicode_at(0)) & 0x7fffffff
	rng.seed = seed_value
	for index in int(settings.count):
		particles.append({
			"position": Vector2(sample("x_range"), sample("y_range")),
			"speed": sample("speed_range"), "phase": rng.randf_range(0, TAU),
			"radius": int(settings.radii[rng.randi_range(0, settings.radii.size() - 1)]),
			"alpha": rng.randi_range(int(settings.alpha_range[0]), int(settings.alpha_range[1]))
		})


func sample(field: String) -> float:
	return rng.randf_range(float(settings[field][0]), float(settings[field][1]))


func step(delta: float) -> void:
	if not is_finite(delta) or delta <= 0:
		return
	elapsed += delta
	for particle in particles:
		particle.position.y -= particle.speed * delta
		particle.position.x += sin(elapsed * settings.drift_speed + particle.phase) * settings.drift_amount * delta
		if particle.position.y < settings.top:
			particle.position = Vector2(sample("x_range"), sample("reset_y_range"))


func snapshot() -> Array[Dictionary]:
	return particles.duplicate(true)
