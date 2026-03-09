from __future__ import annotations

import unittest

from crawler_app.connectors.mihoyo_jobs import MihoyoJobsConnector


class MihoyoConnectorBuildJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = MihoyoJobsConnector()

    def test_build_job_supports_summary_and_delivery_instructions(self) -> None:
        payload = {
            "id": "7901",
            "title": "交互策划（UE）实习生",
            "addressDetailList": [{"addressId": "8", "addressDetail": "上海"}],
            "competencyType": "产品策划类",
            "competencyTypeId": "2",
            "jobNature": "实习",
            "jobNatureId": 3,
            "objectName": "2027届及之后毕业的在校生",
            "projectName": "实习生专项",
            "hireType": 1,
            "hireTypeName": "校园招聘",
            "jobSummary": "加入游戏项目团队，在资深同事的指导下参与具体的交互设计工作，学习游戏界面从设计到落地的完整流程。",
            "description": (
                "1. 负责游戏交互设计，完成需求分析、体验流程梳理，产出原型和说明文档；\n"
                "2. 提供界面视觉表现、操作体验与反馈等方面的创意方案，持续提升界面品质与玩家体验；"
            ),
            "jobRequire": (
                "1. 有扎实的设计专业基础，熟悉体验设计、交互设计、视觉设计的流程和相关理论；\n"
                "2. 熟练掌握Figma、 PS 、 AI等设计工具，有Unity/UE引擎使用经验；"
            ),
            "addition": "",
            "deliveryInstructions": "【必需项】请务必提供个人游戏经历及相关作品。",
            "tagList": [],
            "channelDetailIds": [1, 2],
        }

        job = self.connector._build_job(payload)

        self.assertEqual(job.job_id, "7901")
        self.assertEqual(job.category, "产品策划类")
        self.assertIn("交互设计", job.description)
        self.assertIn("Figma", job.requirements)
        self.assertIn("个人游戏经历", job.delivery_instructions)
        self.assertIn("学习游戏界面从设计到落地", job.summary)
        self.assertEqual(job.tags, [])

    def test_build_job_supports_string_tag_list(self) -> None:
        payload = {
            "id": "7883",
            "title": "机械原画实习生",
            "addressDetailList": [{"addressId": "8", "addressDetail": "上海"}],
            "competencyType": "美术&表现类",
            "competencyTypeId": "3",
            "jobNature": "实习",
            "jobNatureId": 3,
            "objectName": "2027届及之后毕业的在校生",
            "projectName": "实习生专项",
            "hireType": 1,
            "hireTypeName": "校园招聘",
            "jobSummary": "",
            "description": "1.根据游戏世界观、角色设定和玩法需求，设计符合游戏风格且具有辨识度枪械/载具/机械装置的外观；",
            "jobRequire": "1.热爱游戏，对射击游戏有深刻的理解和热情；",
            "addition": "1.掌握3Ds Max/Maya等设计软件，有模型制作、贴图绘制的能力；",
            "deliveryInstructions": "【作品集（必需项）】请选取能体现你专业美术能力的作品。",
            "tagList": ["写实", "硬表面", "机械", "载具"],
            "channelDetailIds": [1],
        }

        job = self.connector._build_job(payload)

        self.assertEqual(job.job_id, "7883")
        self.assertEqual(job.category, "美术&表现类")
        self.assertEqual(job.tags, ["写实", "硬表面", "机械", "载具"])
        self.assertIn("3Ds Max", job.bonus_points)
        self.assertIn("作品集", job.delivery_instructions)


if __name__ == "__main__":
    unittest.main()
