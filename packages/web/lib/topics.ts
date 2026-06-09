// Mirror of packages/composer/nev_composer/renderer.py _TOPIC_META.
// Keep in sync when topics enum changes.

type TopicMeta = { label: string; emoji: string; heading: string };

const TOPIC_META: Record<string, TopicMeta> = {
  sales:              { label: "销量",     emoji: "📊", heading: "📊 销量速览" },
  new_car:            { label: "新车",     emoji: "🚙", heading: "🚙 新车动态" },
  policy:             { label: "政策",     emoji: "📜", heading: "📜 政策法规" },
  overseas:           { label: "海外",     emoji: "🌍", heading: "🌍 海外动态" },
  people:             { label: "人事",     emoji: "👤", heading: "👤 人事变动" },
  finance:            { label: "财务",     emoji: "💰", heading: "💰 财务资本" },
  recall:             { label: "召回",     emoji: "⚠️", heading: "⚠️ 召回质量" },
  supply_chain:       { label: "供应链",   emoji: "🔗", heading: "🔗 供应链" },
  battery_tech:       { label: "电池技术", emoji: "🔋", heading: "🔋 电池技术" },
  autonomous_driving: { label: "智能驾驶", emoji: "🤖", heading: "🤖 智能驾驶" },
  smart_cockpit:      { label: "智能座舱", emoji: "🎙️", heading: "🎙️ 智能座舱" },
  ota_update:         { label: "OTA",     emoji: "📡", heading: "📡 OTA 升级" },
  chassis:            { label: "底盘",     emoji: "🛞", heading: "🛞 底盘操控" },
  exterior_design:    { label: "外观",     emoji: "🎨", heading: "🎨 外观设计" },
  tech:               { label: "技术",     emoji: "🔧", heading: "🔧 通用技术" },
};

const DEFAULT_META: TopicMeta = { label: "其他", emoji: "▫️", heading: "▫️ 其他" };

export function topicLabel(t: string): string {
  return (TOPIC_META[t] ?? DEFAULT_META).label;
}

export function topicEmoji(t: string): string {
  return (TOPIC_META[t] ?? DEFAULT_META).emoji;
}

export function topicHeading(t: string): string {
  return (TOPIC_META[t] ?? DEFAULT_META).heading;
}
