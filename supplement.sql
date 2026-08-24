-- ============================================================
-- 补充数据：缺失的 actions(10-19) + 全部 algorithm_weights
-- 在 Neon SQL Editor 中执行此文件
-- ============================================================

-- ========== 缺失的 actions (第10-19个) ==========
INSERT INTO actions (id, name, description, default_weight) VALUES (10, '站边', '表示支持某名预言家', 1.2);
INSERT INTO actions (id, name, description, default_weight) VALUES (11, '倒钩', '狼人假装好人站边真预言家', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (12, '冲锋', '狼人积极为狼队友号票', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (13, '自爆', '狼人白天自爆身份', 5.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (14, '开枪', '猎人/狼王被淘汰时开枪带人', 3.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (15, '使用解药', '女巫使用解药救人', 2.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (16, '使用毒药', '女巫使用毒药毒人', 2.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (17, '守护', '守卫守护某玩家', 2.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (18, '质疑', '质疑某玩家身份', 1.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (19, '划水', '发言无营养、回避分析', 0.8);

-- ========== 全部 algorithm_weights (209条) ==========
-- 行为1: 跳预言家
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (1, 1, 1, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (2, 1, 2, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (3, 1, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (4, 1, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (5, 1, 5, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (6, 1, 6, 0.6, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (7, 1, 7, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (8, 1, 8, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (9, 1, 9, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (10, 1, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (11, 1, 11, 2.0, 0);

-- 行为2: 查杀
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (12, 2, 1, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (13, 2, 2, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (14, 2, 3, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (15, 2, 4, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (16, 2, 5, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (17, 2, 6, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (18, 2, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (19, 2, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (20, 2, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (21, 2, 10, 0.9, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (22, 2, 11, 0.9, 0);

-- 行为3: 发金水
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (23, 3, 1, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (24, 3, 2, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (25, 3, 3, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (26, 3, 4, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (27, 3, 5, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (28, 3, 6, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (29, 3, 7, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (30, 3, 8, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (31, 3, 9, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (32, 3, 10, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (33, 3, 11, 0.75, 0);

-- 行为4: 跳女巫
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (34, 4, 1, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (35, 4, 2, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (36, 4, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (37, 4, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (38, 4, 5, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (39, 4, 6, 0.6, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (40, 4, 7, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (41, 4, 8, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (42, 4, 9, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (43, 4, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (44, 4, 11, 2.0, 0);

-- 行为5: 跳猎人
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (45, 5, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (46, 5, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (47, 5, 3, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (48, 5, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (49, 5, 5, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (50, 5, 6, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (51, 5, 7, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (52, 5, 8, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (53, 5, 9, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (54, 5, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (55, 5, 11, 1.5, 0);

-- 行为6: 跳守卫
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (56, 6, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (57, 6, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (58, 6, 3, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (59, 6, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (60, 6, 5, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (61, 6, 6, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (62, 6, 7, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (63, 6, 8, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (64, 6, 9, 2.25, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (65, 6, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (66, 6, 11, 1.5, 0);

-- 行为7: 认平民
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (67, 7, 1, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (68, 7, 2, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (69, 7, 3, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (70, 7, 4, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (71, 7, 5, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (72, 7, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (73, 7, 7, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (74, 7, 8, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (75, 7, 9, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (76, 7, 10, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (77, 7, 11, 0.5, 0);

-- 行为8: 投票 (所有身份默认权重1.0)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (78, 8, 1, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (79, 8, 2, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (80, 8, 3, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (81, 8, 4, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (82, 8, 5, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (83, 8, 6, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (84, 8, 7, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (85, 8, 8, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (86, 8, 9, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (87, 8, 10, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (88, 8, 11, 1.0, 0);

-- 行为9: 弃票 (所有身份默认权重0.8)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (89, 9, 1, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (90, 9, 2, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (91, 9, 3, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (92, 9, 4, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (93, 9, 5, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (94, 9, 6, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (95, 9, 7, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (96, 9, 8, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (97, 9, 9, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (98, 9, 10, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (99, 9, 11, 0.8, 0);

-- 行为10: 站边 (所有身份默认权重1.2)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (100, 10, 1, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (101, 10, 2, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (102, 10, 3, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (103, 10, 4, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (104, 10, 5, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (105, 10, 6, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (106, 10, 7, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (107, 10, 8, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (108, 10, 9, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (109, 10, 10, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (110, 10, 11, 1.2, 0);

-- 行为11: 倒钩 (狼人×3, 其他×0.3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (111, 11, 1, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (112, 11, 2, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (113, 11, 3, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (114, 11, 4, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (115, 11, 5, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (116, 11, 6, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (117, 11, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (118, 11, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (119, 11, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (120, 11, 10, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (121, 11, 11, 0.45, 0);

-- 行为12: 冲锋 (狼人×3, 其他×0.3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (122, 12, 1, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (123, 12, 2, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (124, 12, 3, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (125, 12, 4, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (126, 12, 5, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (127, 12, 6, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (128, 12, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (129, 12, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (130, 12, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (131, 12, 10, 0.45, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (132, 12, 11, 0.45, 0);

-- 行为13: 自爆 (狼人×3, 其他×0.3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (133, 13, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (134, 13, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (135, 13, 3, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (136, 13, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (137, 13, 5, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (138, 13, 6, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (139, 13, 7, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (140, 13, 8, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (141, 13, 9, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (142, 13, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (143, 13, 11, 1.5, 0);

-- 行为14: 开枪 (猎人/狼王×3, 其他默认)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (144, 14, 1, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (145, 14, 2, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (146, 14, 3, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (147, 14, 4, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (148, 14, 5, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (149, 14, 6, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (150, 14, 7, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (151, 14, 8, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (152, 14, 9, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (153, 14, 10, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (154, 14, 11, 3.0, 0);

-- 行为15: 使用解药 (女巫×3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (155, 15, 1, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (156, 15, 2, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (157, 15, 3, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (158, 15, 4, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (159, 15, 5, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (160, 15, 6, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (161, 15, 7, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (162, 15, 8, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (163, 15, 9, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (164, 15, 10, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (165, 15, 11, 2.5, 0);

-- 行为16: 使用毒药 (女巫×3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (166, 16, 1, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (167, 16, 2, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (168, 16, 3, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (169, 16, 4, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (170, 16, 5, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (171, 16, 6, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (172, 16, 7, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (173, 16, 8, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (174, 16, 9, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (175, 16, 10, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (176, 16, 11, 2.5, 0);

-- 行为17: 守护 (守卫×3)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (177, 17, 1, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (178, 17, 2, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (179, 17, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (180, 17, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (181, 17, 5, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (182, 17, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (183, 17, 7, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (184, 17, 8, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (185, 17, 9, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (186, 17, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (187, 17, 11, 2.0, 0);

-- 行为18: 质疑 (所有身份默认1.0)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (188, 18, 1, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (189, 18, 2, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (190, 18, 3, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (191, 18, 4, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (192, 18, 5, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (193, 18, 6, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (194, 18, 7, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (195, 18, 8, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (196, 18, 9, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (197, 18, 10, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (198, 18, 11, 1.0, 0);

-- 行为19: 划水 (所有身份默认0.8)
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (199, 19, 1, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (200, 19, 2, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (201, 19, 3, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (202, 19, 4, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (203, 19, 5, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (204, 19, 6, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (205, 19, 7, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (206, 19, 8, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (207, 19, 9, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (208, 19, 10, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (209, 19, 11, 0.8, 0);

-- ========== 修复自增序列 ==========
SELECT setval('actions_id_seq', (SELECT MAX(id) FROM actions));
SELECT setval('algorithm_weights_id_seq', (SELECT MAX(id) FROM algorithm_weights));

-- ========== 补充完成 ==========
