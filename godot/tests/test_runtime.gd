extends SceneTree

const ContentLoader = preload("res://scripts/content_loader.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
var failures: Array[String] = []
var checks: int = 0


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func _initialize() -> void:
	call_deferred("run_tests")


func run_tests() -> void:
	var loader := ContentLoader.new()
	var root := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var data := loader.load_project(root)
	check(not data.is_empty(), "Shared source content loads: " + loader.error)
	if data.is_empty():
		finish()
		return
	check(data.characters.size() == 2 and data.objects.size() == 5, "Current characters and placements are shared")
	check(not data.objects.back().definition.visible, "Game device remains hidden")
	check(loader.path_for("../outside.json").is_empty(), "Root escape is rejected")
	loader.error = ""
	check(loader.path_for("C:/outside.json").is_empty(), "Absolute path is rejected")
	loader.error = ""
	check(not loader.finite_number(NAN) and not loader.finite_number(INF), "Nonfinite numbers are rejected")
	var definition: Dictionary = data.characters[0].definition
	var bounds := Rect2(74, 80, 812, 446)
	var water := Rect2(335, 348, 354, 168)
	var size := Vector2(64, 64)
	var one := GhostModel.new(definition, size, bounds, water, 12345)
	var two := GhostModel.new(definition, size, bounds, water, 12345)
	var partner := GhostModel.new(data.characters[1].definition, size, bounds, water, 12345)
	for frame in 1200:
		one.step(1.0 / 60)
		for extra in 5:
			partner.rng.randf()
		partner.step(1.0 / 60)
		two.step(1.0 / 60)
	check(one.snapshot() == two.snapshot(), "Partner draws cannot change another ghost's RNG/state")
	check(partner.native_facing == -1, "Maru source faces left")
	var stayed_inside := true
	var stayed_forward := true
	for frame in 18000:
		for ghost in [one, partner]:
			ghost.step(1.0 / 60)
			stayed_inside = stayed_inside and ghost.position.x >= ghost.bounds.position.x - 0.01 and ghost.position.x <= ghost.bounds.end.x + 0.01 and ghost.position.y >= ghost.bounds.position.y - 0.01 and ghost.position.y <= ghost.bounds.end.y + 0.01
			if not ghost.turning and ghost.action != "loop":
				stayed_forward = stayed_forward and ghost.velocity.x * ghost.facing >= -0.01
	check(stayed_inside, "Long random walk remains inside movement bounds")
	check(stayed_forward, "Long random walk only moves toward its facing")
	one.position = Vector2(300, 380)
	one.action = "forward"
	one.action_timer = 10
	one.facing = 1
	one.turning = false
	one.set_velocity(Vector2(-30, 0))
	var before := one.position
	one.step(0.3)
	check(one.position == before and one.turning, "Turn before backward movement")
	one.step(0.3)
	one.step(0.1)
	check(one.facing == -1 and one.position.x < before.x, "Advance after completed turn")
	for direction in [-1, 1]:
		one.position = Vector2(480, 380)
		one.facing = direction
		one.turning = false
		one.target = null
		check(one.begin_loop(), "Loop has room in direction " + str(direction))
		var start := one.position
		var duration := one.loop_duration
		var travel := one.loop_travel
		one.step(duration * 0.25)
		check(is_equal_approx(one.angle, -direction * PI * 0.5) and one.position.y < start.y, "First quarter rotates with travel direction")
		one.go_to(Vector2(480, 200))
		one.step(duration * 0.25)
		check(one.action == "loop" and is_equal_approx(absf(one.angle), PI), "Click does not interrupt a loop")
		one.step(duration * 0.5)
		check(one.action == "forward" and is_zero_approx(one.angle) and is_equal_approx(one.position.x, start.x + direction * travel), "Exactly one travelling revolution")
	one.position = Vector2(one.bounds.end.x - 1, 260)
	one.target = null
	one.action = "forward"
	one.action_timer = 10
	one.facing = 1
	one.turning = false
	one.set_velocity(Vector2(150, 0))
	one.step(5.0)
	check(one.position.x <= one.bounds.end.x and one.turning, "Large delta stays inside wall and begins reflection turn")
	var zero_weights: Dictionary = definition.duplicate(true)
	zero_weights.behavior_weights = {}
	for action in GhostModel.ACTIONS:
		zero_weights.behavior_weights[action] = 0
	var idle := GhostModel.new(zero_weights, size, bounds, water, 12345)
	idle.choose_action()
	check(idle.action == "stop" and idle.velocity == Vector2.ZERO, "All disabled actions safely stop")
	var stationary := idle.position
	var floating := idle.draw_position()
	idle.step(0.7)
	check(idle.position == stationary and idle.draw_position() != floating, "Stopped ghost only bobs slowly")
	idle.weights["water_stop"] = 1
	idle.position = water.get_center()
	idle.choose_action()
	check(idle.action == "water_stop" and idle.velocity == Vector2.ZERO, "Water stop can be selected inside water zone")
	idle.position = Vector2(200, 200)
	idle.choose_action()
	check(idle.action == "stop", "Water stop is not selected away from water")
	one.position = Vector2(400, 270)
	one.turning = false
	one.action = "forward"
	one.go_to(Vector2(540, 270))
	for frame in 600:
		one.step(1.0 / 60)
		if one.target == null:
			break
	check(one.target == null and one.position.distance_to(Vector2(540, 270)) < 0.01, "Click reaches target and returns to AI")
	var scene := load("res://main.tscn") as PackedScene
	var game := scene.instantiate()
	get_root().add_child(game)
	game.set_process(false)
	game.send_click(Vector2.ZERO)
	var first: Vector2 = game.ghosts[0].target
	var second: Vector2 = game.ghosts[1].target
	check(is_equal_approx(absf(first.x - second.x), 120) and is_equal_approx(first.y, second.y), "Wall click preserves side-by-side spacing")
	game.free()
	finish()


func finish() -> void:
	print("GODOT_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
