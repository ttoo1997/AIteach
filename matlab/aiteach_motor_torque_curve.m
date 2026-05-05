function [slip, torque, max_slip, max_torque, start_torque] = aiteach_motor_torque_curve(r2, x2, e2, s_min, s_max, n_points)
% AITEACH_MOTOR_TORQUE_CURVE
% 默认 MATLAB 版本的异步电机教学仿真函数。
% 后续可以把这里替换为 Simulink 模型调用，保持输入输出接口不变。

slip = linspace(s_min, s_max, n_points);
torque = (slip .* (e2 .^ 2) .* r2) ./ (r2 .^ 2 + (slip .* x2) .^ 2);
[max_torque, idx] = max(torque);
max_slip = slip(idx);
start_torque = torque(end);
