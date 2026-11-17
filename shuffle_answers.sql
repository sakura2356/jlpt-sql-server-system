USE jlpt_db;
GO

IF EXISTS (SELECT 1 FROM dbo.Questions WHERE question_id = 2 AND correct_answer = 'A')
BEGIN
    -- 1. 題號除以 4 餘 2 -> 正解改為 B（交換選項 A 與 B）
    UPDATE dbo.Questions
    SET option_a = option_b,
        option_b = option_a,
        correct_answer = 'B',
        explanation = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(explanation, N'選 A', N'選 B'), N'(A正確)', N'(B正確)'), N'對應 A', N'對應 B'), N' A 正確', N' B 正確'), N'為 A', N'為 B')
    WHERE question_id % 4 = 2 AND question_id <> 33;

    -- 2. 題號除以 4 餘 3 -> 正解改為 C（交換選項 A 與 C）
    UPDATE dbo.Questions
    SET option_a = option_c,
        option_c = option_a,
        correct_answer = 'C',
        explanation = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(explanation, N'注意 C 與 D', N'注意 A 與 D'), N'選 A', N'選 C'), N'(A正確)', N'(C正確)'), N'對應 A', N'對應 C'), N' A 正確', N' C 正確'), N'為 A', N'為 C')
    WHERE question_id % 4 = 3;

    -- 3. 題號除以 4 餘 0 -> 正解改為 D（交換選項 A 與 D）
    UPDATE dbo.Questions
    SET option_a = option_d,
        option_d = option_a,
        correct_answer = 'D',
        explanation = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(explanation, N'選 A', N'選 D'), N'(A正確)', N'(D正確)'), N'對應 A', N'對應 D'), N' A 正確', N' D 正確'), N'為 A', N'為 D')
    WHERE question_id % 4 = 0;

    -- 4. 同步更新歷史作答明細 Test_Details 的選項代號，確保關聯資料 100% 吻合
    UPDATE td
    SET td.user_choice = CASE
        WHEN q.question_id % 4 = 2 AND q.question_id <> 33 AND td.user_choice = 'A' THEN 'B'
        WHEN q.question_id % 4 = 2 AND q.question_id <> 33 AND td.user_choice = 'B' THEN 'A'
        WHEN q.question_id % 4 = 3 AND td.user_choice = 'A' THEN 'C'
        WHEN q.question_id % 4 = 3 AND td.user_choice = 'C' THEN 'A'
        WHEN q.question_id % 4 = 0 AND td.user_choice = 'A' THEN 'D'
        WHEN q.question_id % 4 = 0 AND td.user_choice = 'D' THEN 'A'
        ELSE td.user_choice
    END
    FROM dbo.Test_Details td
    JOIN dbo.Questions q ON td.question_id = q.question_id;
END
GO