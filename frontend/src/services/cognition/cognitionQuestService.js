/**
 * Cognition Quest Service (Mock) - JavaScript entry for React components
 * ECTA Quest - hybrid Oxigraph + Document DB architecture.
 * TypeScript version: cognitionQuestService.ts
 */

export class CognitionQuestService {
  static async getMacroStructure() {
    // Hardcoded from knowledge_graph/quest_full.ttl - 认知发展篇, grouped by recommendedAgeBracket
    return [
      {
        ageBracket: '3-12个月',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_002', label: '002 学习控制自己的身体' },
          { uri_id: 'ecta-inst:obj_cog_003', label: '003 开始操控物件' },
          { uri_id: 'ecta-inst:obj_cog_005', label: '005 开始发展物件存在的概念' },
          { uri_id: 'ecta-inst:obj_cog_006', label: '006 尝试用声音以及动作表达' },
          { uri_id: 'ecta-inst:obj_cog_038', label: '038 发展进一步的分类概念' },
          { uri_id: 'ecta-inst:obj_cog_040', label: '040 理解事情或动作上的先后次序' },
          { uri_id: 'ecta-inst:obj_cog_041', label: '041 明白相对性的概念及词语' },
          { uri_id: 'ecta-inst:obj_cog_044', label: '044 明白简单的数量概念' }
        ]
      },
      {
        ageBracket: '1-2岁',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_007a', label: '007a 发展注视眼前事物的能力' },
          { uri_id: 'ecta-inst:obj_cog_007b', label: '007b 发展视觉的追视能力' },
          { uri_id: 'ecta-inst:obj_cog_008', label: '008 发展视觉的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_011', label: '011 发展对声音的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_012', label: '012 发展对味道的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_013', label: '013 开始发展物件不变的概念' },
          { uri_id: 'ecta-inst:obj_cog_016', label: '016 认识与自己有关的事物' },
          { uri_id: 'ecta-inst:obj_cog_018', label: '018 学会常用物件的名称以及功用' },
          { uri_id: 'ecta-inst:obj_cog_020', label: '020 学会简单的类别概念' },
          { uri_id: 'ecta-inst:obj_cog_021', label: '021 学会简单因果关系' },
          { uri_id: 'ecta-inst:obj_cog_022', label: '022 学习物件在空间上的位置及先后次序' },
          { uri_id: 'ecta-inst:obj_cog_024', label: '024 会使用工具解决空间问题' }
        ]
      },
      {
        ageBracket: '2-3岁',
        objectives: [
          { uri_id: 'ecta-inst:obj_cog_025a', label: '025a 发展对视觉刺激的专注力' },
          { uri_id: 'ecta-inst:obj_cog_025b', label: '025b 发展对视觉刺激的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_028a', label: '028a 发展对声音的辨别能力' },
          { uri_id: 'ecta-inst:obj_cog_028b', label: '028b 辨别来自身体的感觉' },
          { uri_id: 'ecta-inst:obj_cog_029', label: '029 发展将物件符号化的能力' },
          { uri_id: 'ecta-inst:obj_cog_032', label: '032 认识物件的特性' },
          { uri_id: 'ecta-inst:obj_cog_036', label: '036 知道物件与物件之间的关系' }
        ]
      }
    ];
  }

  static async getUnlockedQuests(completedUris) {
    // Mock data based on ABA handbook - ECTA color matching tasks
    return [
      {
        uri_id: 'ecta-inst:task_color_match_identical',
        title: '基础颜色配对 (相同颜色、形状)',
        materials: ['红色积木', '蓝色积木', '篮子'],
        environments: {
          structured_desktop: {
            steps: [
              '导师拿出颜色相同、形状相同的一组物件',
              '指令: 一样的颜色放一起'
            ],
            fading_prompts: {
              hard: ['全辅助: 拿着孩子的手放'],
              good: [],
              easy: ['独立完成']
            }
          },
          group_social: ['课前将相同颜色的成套座椅对应摆放'],
          home_natural: ['按颜色对头饰进行分类', '整理床品四件套']
        }
      },
      {
        uri_id: 'ecta-inst:task_color_match_distractor',
        title: '抗干扰颜色配对 (增加干扰物)',
        materials: ['红色积木', '蓝色积木', '黄色雪花片'],
        environments: {
          structured_desktop: {
            steps: [
              '在桌面加入与目标颜色不同的干扰物',
              '指令: 把红色/蓝色的放一起'
            ],
            fading_prompts: {
              hard: ['全辅助: 指认干扰物并排除'],
              good: ['部分辅助: 口头提示'],
              easy: ['独立完成']
            }
          },
          group_social: ['小组活动中按颜色分组，有干扰物混入'],
          home_natural: ['整理玩具时排除不同颜色的物品', '按颜色叠放衣物']
        }
      }
    ];
  }

  static async getQuestDetails(uri) {
    return null;
  }
}
