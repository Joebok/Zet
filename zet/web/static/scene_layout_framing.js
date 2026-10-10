// Normalized image coordinates use a top-left origin, matching the backend crop.
export function backgroundCrop(width, height, aspect, framing = {}) {
  const zoom = Math.min(20, Math.max(.05, Number(framing.zoom ?? 1)));
  const imageAspect = width / height;
  const w = Math.min(1, aspect / imageAspect) / zoom;
  const h = Math.min(1, imageAspect / aspect) / zoom;
  const center = framing.center || [.5, .5];
  const x = Math.min(5, Math.max(-5, center[0]));
  const y = Math.min(5, Math.max(-5, center[1]));
  return { left: x - w / 2, top: y - h / 2, width: w, height: h, center: [x, y], zoom };
}

export function groundFrame(layout) {
  const camera = layout.cameras.find((item) => item.id === layout.active_camera_id);
  const position = camera.position;
  const direction = camera.target.map((value, index) => value - position[index]);
  const length = Math.max(1e-6, Math.hypot(...direction));
  const forward = direction.map((value) => value / length);
  const horizontalLength = Math.hypot(forward[0], forward[2]);
  const horizontal = horizontalLength > 1e-6 ? [forward[0] / horizontalLength, 0, forward[2] / horizontalLength] : [0, 0, -1];
  const right = horizontalLength > 1e-6 ? [-forward[2] / horizontalLength, 0, forward[0] / horizontalLength] : [1, 0, 0];
  const up = [-right[2] * forward[1], right[2] * forward[0] - right[0] * forward[2], right[0] * forward[1]];
  const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
  const depths = (layout.pawns || []).map((pawn) => dot(pawn.position.map((value, index) => value - position[index]), horizontal));
  const minimum = Math.max(1, ...depths.map((depth, index) => depth + Math.max(layout.pawns[index].dimensions.depth, layout.pawns[index].dimensions.width) / 2 + .02));
  const distance = camera.ground_distance_m || Math.max(10, ...depths.map((depth) => depth + 5));
  const tangent = Math.tan(camera.vertical_fov * Math.PI / 360);
  const joinAt = (value) => {
    const relative = horizontal.map((axis, index) => axis * value - (index === 1 ? position[1] : 0));
    return (1 - dot(relative, up) / (Math.max(1e-5, dot(relative, forward)) * tangent)) / 2;
  };
  const clamp = (value) => Math.min(1, Math.max(0, value));
  const join = joinAt(distance);
  const enabled = layout.ground?.enabled !== false;
  return { enabled, distance_m: distance, minimum_distance_m: minimum, join_y: enabled ? join : 1, visible_fraction: enabled ? clamp(join) : 1,
    join_min: clamp(joinAt(Math.max(1000, minimum + 1))), join_max: clamp(joinAt(minimum)),
    origin: position.map((value, index) => value + horizontal[index] * distance - (index === 1 ? position[1] : 0)),
    forward: horizontal, color: [185, 176, 160] };
}

export function distanceForGroundJoin(camera, join) {
  const direction = camera.target.map((value, index) => value - camera.position[index]);
  const length = Math.max(1e-6, Math.hypot(...direction));
  const sin = direction[1] / length;
  const cos = Math.hypot(direction[0], direction[2]) / length;
  const ny = (1 - 2 * join) * Math.tan(camera.vertical_fov * Math.PI / 360);
  const denominator = ny * cos + sin;
  return Math.abs(denominator) < 1e-6 ? 1000 : camera.position[1] * (ny * sin - cos) / denominator;
}
