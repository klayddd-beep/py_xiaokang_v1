#!/usr/bin/env bash

set -u

USB_KEYWORD="${1:-UACDemoV1.0}"
TARGET_VOLUME="${TARGET_VOLUME:-80%}"

log() {
  echo "[usb-audio-fix] $*"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

set_alsa_levels() {
  if ! has_cmd amixer; then
    return 0
  fi

  local card_index=""
  if has_cmd aplay; then
    card_index="$(aplay -l 2>/dev/null | awk -v kw="$USB_KEYWORD" '$0 ~ kw {gsub(":", "", $2); print $2; exit}')"
  fi

  if [[ -z "$card_index" ]] && has_cmd arecord; then
    card_index="$(arecord -l 2>/dev/null | awk -v kw="$USB_KEYWORD" '$0 ~ kw {gsub(":", "", $2); print $2; exit}')"
  fi

  if [[ -z "$card_index" ]]; then
    log "未找到 ALSA USB 声卡，跳过 amixer 兜底"
    return 0
  fi

  local controls=(Speaker PCM Master Headphone Mic Capture)
  local control
  for control in "${controls[@]}"; do
    amixer -c "$card_index" sset "$control" "$TARGET_VOLUME" unmute >/dev/null 2>&1 || true
  done
  log "ALSA($card_index) 音量兜底完成"
}

set_pulse_defaults() {
  if ! has_cmd pactl; then
    log "未检测到 pactl，跳过 PulseAudio 设置"
    return 1
  fi

  if ! pactl info >/dev/null 2>&1; then
    log "pactl 无法连接音频服务，跳过 PulseAudio 设置"
    return 1
  fi

  local sink=""
  local source=""

  sink="$(pactl list short sinks | awk -v kw="$USB_KEYWORD" '$2 ~ kw {print $2; exit}')"
  if [[ -z "$sink" ]]; then
    sink="$(pactl list short sinks | awk '$2 ~ /usb/i {print $2; exit}')"
  fi

  source="$(pactl list short sources | awk -v kw="$USB_KEYWORD" '$2 ~ kw && $2 !~ /\.monitor$/ {print $2; exit}')"
  if [[ -z "$source" ]]; then
    source="$(pactl list short sources | awk '$2 ~ /usb/i && $2 !~ /\.monitor$/ {print $2; exit}')"
  fi

  if [[ -n "$sink" ]]; then
    pactl set-default-sink "$sink" || true
    pactl set-sink-mute "$sink" 0 || true
    pactl set-sink-volume "$sink" "$TARGET_VOLUME" || true
    log "默认输出已设为: $sink ($TARGET_VOLUME)"
  else
    log "未找到 USB sink，保持当前默认输出"
  fi

  if [[ -n "$source" ]]; then
    pactl set-default-source "$source" || true
    pactl set-source-mute "$source" 0 || true
    pactl set-source-volume "$source" "$TARGET_VOLUME" || true
    log "默认输入已设为: $source ($TARGET_VOLUME)"
  else
    log "未找到 USB source，保持当前默认输入"
  fi

  if [[ -n "$sink" || -n "$source" ]]; then
    return 0
  fi

  return 1
}

main() {
  log "开始修复 USB 音频默认路由，关键字: $USB_KEYWORD"

  if set_pulse_defaults; then
    set_alsa_levels
    log "USB 音频修复完成"
    return 0
  fi

  set_alsa_levels
  log "仅执行了 ALSA 兜底（无 PulseAudio/PipeWire-pulse）"
}

main "$@"
