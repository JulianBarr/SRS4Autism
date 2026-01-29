// CUMA Logic City Data
// This file must be placed in Anki's collection.media folder
// The underscore prefix prevents Anki's media cleaner from removing it
// Format: window.CUMA_DATA = { "category": ["word1", "word2", ...], ... }

window.CUMA_DATA = {
  "kitchen": ["碗", "盘", "勺", "筷子", "杯子", "锅", "刀", "叉"],
  "fruit": ["苹果", "香蕉", "葡萄", "橙子", "草莓", "西瓜", "梨", "桃子"],
  "animal": ["狗", "猫", "鸟", "鱼", "兔子", "马", "牛", "羊"],
  "body": ["头", "手", "脚", "眼睛", "鼻子", "嘴巴", "耳朵", "腿"],
  "color": ["红", "蓝", "绿", "黄", "黑", "白", "紫", "橙"],
  "vehicle": ["车", "飞机", "船", "自行车", "火车", "公交车", "摩托车", "卡车"],
  "clothing": ["衣服", "裤子", "鞋子", "帽子", "袜子", "裙子", "外套", "衬衫"],
  "all_words": [] // Will be auto-populated from all categories
};

// Auto-populate all_words array
(function() {
  var all = [];
  for (var category in window.CUMA_DATA) {
    if (category !== "all_words" && Array.isArray(window.CUMA_DATA[category])) {
      all = all.concat(window.CUMA_DATA[category]);
    }
  }
  // Remove duplicates
  window.CUMA_DATA.all_words = Array.from(new Set(all));
})();

