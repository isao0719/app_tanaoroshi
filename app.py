import pandas as pd
import numpy as np
import mojimoji
import re
import streamlit as st
import glob  # 重複チェックで使用


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True


def cleansing_naka(df):
    df.columns = ["load薬品名", "load包装", "JANコード", "load納入価"]  # カラム名変更（念のため）

    df["naka薬品名"] = df["load薬品名"].str.cat(df["load包装"])  # 医薬品名を結合
    df["naka薬品名"] = df["naka薬品名"].str.replace(" ", "")
    df["naka薬品名"] = df["naka薬品名"].apply(
        mojimoji.han_to_zen, digit=False, ascii=False
    )  # digit引数で数字は全角変換数字を除外
    # 包装単位を抽出して単位納入価を導き出す
    pattan_last_int = "\d+"

    def extract_tanni(x):
        res = re.findall(pattan_last_int, x["load包装"])[-1:]  # 数字を抽出
        x["包装単位"] = res[0]
        return x["包装単位"]

    df["包装単位"] = df.apply(extract_tanni, axis=1)  # 薬価の確認が必要

    # 正規表現を使用して、指定されたパターンに一致する部分を抽出
    pattern = r"(.*)X"
    df["包装規格name"] = df["load包装"].str.extract(pattern, expand=False)
    df.fillna({"包装規格name": "1"}, inplace=True)  # Nanを1にする
    df.dropna(inplace=True)  # 念のためNanを消す

    # 包装「X」の前の数字を抽出
    pattan_last_float = "([0-9]+\.?[0-9]*)"

    def extract_tanni(x):
        x["包装規格name"] = "1a" + x["包装規格name"]  # 数字を含まない行がある為、"1a"をたす
        res = re.findall(pattan_last_float, x["包装規格name"])[-1:]  # 数字を抽出
        x["包装規格"] = res[0]
        return x["包装規格"]

    df["包装規格"] = df.apply(extract_tanni, axis=1)

    # naka単価を計算
    df["包装単位"] = df["包装単位"].astype(float)
    df["包装規格"] = df["包装規格"].astype(float)

    def tanka_cal(x):
        res = x["load納入価"] / x["包装単位"] / x["包装規格"]
        return res

    df["naka単価"] = df.apply(tanka_cal, axis=1)  # apply適用

    # 一覧単位薬価と中北単位薬価の相違をなくす　#目薬の薬価単位（本）と吸入はしていない
    # 注射　炭酸ランタン顆粒分包　　の単位薬価は　×をしない
    df["単価調整_flag"] = df["naka薬品名"].str.contains("注|炭酸ランタン顆粒分包")
    query_str = "単価調整_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "naka単価"] = df["naka単価"] * df["包装規格"]  # 単位薬価の調整

    # naka_check薬品名を作成する
    # 『PTP』の処理
    df["name_flag"] = df["naka薬品名"].str.contains("PTP")

    def change_gene(x):
        if x["name_flag"] == 1:
            return x["naka薬品名"].split("PTP")[0]  # 「」の後ろ文字がいらない
        else:
            pass

    df["check_naka薬品名"] = df.apply(
        change_gene, axis=1
    )  # ジェネリック医薬品名を変換してcheck_suzu薬品名にした

    # 『%』の処理
    df["name導入_flag"] = df["naka薬品名"].str.contains("%")

    def change_percent(x):
        if x["name導入_flag"] == 1:
            return x["naka薬品名"].split("%")[0]
        else:
            pass

    df["change1薬品名"] = df.apply(change_percent, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした

    # 処理済は"name導入_flag　をFalseにする
    # name導入_flag 変換関数
    def name_flag_change(x):
        if x["name_flag"] == True:
            x["name導入_flag"] = False

        else:
            x["name導入_flag"] = x["name導入_flag"]
        return x["name導入_flag"]

    df["name導入_flag"] = df.apply(name_flag_change, axis=1)

    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "check_naka薬品名"] = df["change1薬品名"] + "%"  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = True  # 引き渡した医薬品名はTureに変換

    # 『mg』の処理
    df["name導入_flag"] = df["naka薬品名"].str.contains("mg")

    def change_mg(x):
        if x["name導入_flag"] == 1:
            return x["naka薬品名"].split("mg")[0]
        else:
            pass

    df["change1薬品名"] = df.apply(change_mg, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした

    # 処理済は"name導入_flag　をFalseにする
    # name導入_flag 変換関数
    def name_flag_change(x):
        if x["name_flag"] == True:
            x["name導入_flag"] = False

        else:
            x["name導入_flag"] = x["name導入_flag"]
        return x["name導入_flag"]

    df["name導入_flag"] = df.apply(name_flag_change, axis=1)

    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "check_naka薬品名"] = df["change1薬品名"] + "mg"  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = True  # 引き渡した医薬品名はTureに変換

    # 未変換naka薬品名のcheck_naka薬品名に埋め込む
    def remaining_name(x):
        if x["name_flag"] == False:
            x["check_naka薬品名"] = x["naka薬品名"]

        else:
            x["check_naka薬品名"] = x["check_naka薬品名"]
        return x["check_naka薬品名"]

    df["check_naka薬品名"] = df.apply(remaining_name, axis=1)

    # df_select = df[["JANコード","naka薬品名","check_naka薬品名","naka単価"]]
    df = df[["JANコード", "naka薬品名", "check_naka薬品名", "naka単価"]]

    return df


# スズケンの前処理
def cleansing_suzu(df):
    df.columns = ["JANコード", "load薬品名", "load包装", "load納入価"]  # カラム名変更（念のため）
    # エクセルデータ　を変換
    df["suzu薬品名"] = df["load薬品名"].str.cat(df["load包装"])  # 医薬品名を結合
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("", "mg")  # 認識されない文字を変換
    # 元データが『mg』だと思われるものが変換された・・なので他も変換
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("", "g")  # 『？』はVSコード内でコピペ
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("", "枚")
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("", "袋")
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("", "μｇ")

    df["suzu薬品名"] = df["suzu薬品名"].str.replace(" ", "")
    df["suzu薬品名"] = df["suzu薬品名"].apply(
        mojimoji.han_to_zen, digit=False, ascii=False
    )  # 数字と英語は半角、カナ文字と漢字は全角
    df["suzu薬品名"] = df["suzu薬品名"].str.replace("-", "ー")

    # 包装単位を抽出して単位納入価を導き出す
    pattan_last_int = "\d+"

    def extract_tanni(x):
        res = re.findall(pattan_last_int, x["load包装"])[-1:]  # 数字を抽出
        x["包装単位"] = res[0]
        return x["包装単位"]

    df["包装単位"] = df.apply(extract_tanni, axis=1)  # 薬価の確認が必要

    # 正規表現を使用して、指定されたパターンに一致する部分を抽出
    pattern = r"(.*)X"
    df["包装規格name"] = df["suzu薬品名"].str.extract(pattern, expand=False)
    df.fillna({"包装規格name": "1"}, inplace=True)  # Nanを1にする
    df.dropna(inplace=True)

    pattan_last_float = "([0-9]+\.?[0-9]*)"

    # 包装「X」の前の数字を抽出
    def extract_tanni(x):
        x["包装規格name"] = "1a" + x["包装規格name"]  # 数字を含まない行がある為、"1a"をたす
        res = re.findall(pattan_last_float, x["包装規格name"])[-1:]  # 数字を抽出
        x["包装規格"] = res[0]
        return x["包装規格"]

    df["包装規格"] = df.apply(extract_tanni, axis=1)

    # suzu単価を計算
    df["包装単位"] = df["包装単位"].astype(float)
    df["包装規格"] = df["包装規格"].astype(float)

    def tanka_cal(x):
        res = x["load納入価"] / x["包装単位"] / x["包装規格"]
        return res

    df["suzu単価"] = df.apply(tanka_cal, axis=1)  # apply適用

    # 一覧単位薬価とスズケン単位薬価の相違をなくす
    # 注射　メプチン吸入　モメタゾン点鼻　ネオキシテープ　　の単位薬価は　×をしない
    list_mihenkan = [
        "注",
        "吸入",
        "ネオキシテープ",
        "カリメート経口液",
        "ラグノスNF経口ゼリー",
        "点鼻液",
        "エアゾール",
        "ラクリミン点眼液",
        "サンコバ点眼液",
        "ジクアス点眼液",
        "ヒアレイン点眼液",
        "リーバクト配合顆粒",
        "ピレノキシン懸濁性点眼液",
    ]
    mihennkan = "|".join(list_mihenkan)
    df["単価調整_flag"] = df["suzu薬品名"].str.contains(mihennkan)
    query_str = "単価調整_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "suzu単価"] = df["suzu単価"] * df["包装規格"]  # 単位薬価の調整

    # ツムラ漢方でｘが２つある場合　、単位薬価は　×２をする
    df["ツムラ調整単価"] = 1
    pattan_before_g = "([0-9]+\.?[0-9]*)g"

    # 包装「X」の前の数字を抽出
    def tumura_tanni(x):
        x["包装規格name"] = "1g" + x["包装規格name"]  # 数字を含まない行がある為、"1g"をたす
        res = re.findall(pattan_before_g, x["包装規格name"])[-1:]  # 数字を抽出
        x["ツムラ調整単価"] = res[0]
        return x["ツムラ調整単価"]

    df["ツムラ調整単価"] = df.apply(tumura_tanni, axis=1)
    df["ツムラ単価調整_flag"] = df["包装規格name"].str.contains("ツムラ") & df[
        "包装規格name"
    ].str.contains("X")

    query_str = "ツムラ単価調整_flag == 1"
    df_subset = df.query(query_str)
    df["ツムラ調整単価"] = df["ツムラ調整単価"].astype(float)
    df.loc[df_subset.index, "suzu単価"] = df["suzu単価"] / df["ツムラ調整単価"]  # 単位薬価の調整

    # suzu_check薬品名を作成する
    # 『「」』の処理
    df["name_flag"] = df["suzu薬品名"].str.contains("」")

    def change_gene(x):
        if x["name_flag"] == 1:
            return x["suzu薬品名"].split("」")[0] + "」"  # 「」の後ろ文字がいらない
        else:
            pass

    df["check_suzu薬品名"] = df.apply(
        change_gene, axis=1
    )  # ジェネリック医薬品名を変換してcheck_suzu薬品名にした

    # 『mg』の処理
    df["name導入_flag"] = df["suzu薬品名"].str.contains("mg")

    def change_mg(x):
        if x["name導入_flag"] == 1:
            return x["suzu薬品名"].split("mg")[0]
        else:
            pass

    df["change1薬品名"] = df.apply(change_mg, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした

    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "check_suzu薬品名"] = df["change1薬品名"] + "mg"  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = True  # 引き渡した医薬品名はTureに変換

    def change_percent(x):
        if x["name_flag"] == 0:
            return x["suzu薬品名"].split("%")[0]
        else:
            pass

    df["change1薬品名"] = df.apply(change_percent, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした

    # 『%』の処理
    df["name導入_flag"] = df["suzu薬品名"].str.contains("%")  # 医薬品に"%"をもつ導入カラムを作成

    # 『「」』と　『mg』の処理済は"name導入_flag　をFalseにする
    # name導入_flag 変換関数
    def name_flag_change(x):
        if x["name_flag"] == True:
            x["name導入_flag"] = False

        else:
            x["name導入_flag"] = x["name導入_flag"]
        return x["name導入_flag"]

    df["name導入_flag"] = df.apply(name_flag_change, axis=1)

    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "check_suzu薬品名"] = df["change1薬品名"] + "%"  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = True  # 引き渡した医薬品名はfalseに変換
    # check医薬品名未変換している　「漢方」「ヒート」

    # df_select = df[["JANコード","suzu薬品名","check_suzu薬品名","suzu単価"]]
    df = df[["JANコード", "suzu薬品名", "check_suzu薬品名", "suzu単価"]]

    return df


# メディセオの前処理
def cleansing_medi(df):
    df.columns = ["JANコード", "load薬品名", "load包装", "medi単価"]  # カラム名変更（念のため）
    # メディセオ　全角半角処理
    df["medi薬品名"] = df["load薬品名"].str.cat(df["load包装"])  # 医薬品名を結合
    df.drop(columns=["load薬品名", "load包装"], inplace=True)  # カラム整理の為、drop
    df["medi薬品名"] = df["medi薬品名"].apply(
        mojimoji.han_to_zen, digit=False, ascii=False
    )  ##数字と英語は半角、カナ文字と漢字は全角

    # Mとgは数字後の規格あわせの為、名称にMとGが入っている場合に注意
    df["medi薬品名"] = (
        df["medi薬品名"]
        .str.replace(" ", "")
        .str.replace("M", "m")
        .str.replace("G", "g")
        .str.replace("-", "ー")
    )
    # change1薬品名の文字、包装部分を削除していく
    df["change1薬品名"] = df["medi薬品名"].str.extract(r"(.*)PTP", expand=False)  # PTPの処理
    df["name_flag"] = df[
        "change1薬品名"
    ].isnull()  # 変換できなかったデータの確認 ※name_flag=Falseが医薬品名変更終了

    # Mとgは数字後の規格あわせの為、名称にMとGが入っている場合に注意
    df["medi薬品名"] = (
        df["medi薬品名"]
        .str.replace(" ", "")
        .str.replace("M", "m")
        .str.replace("G", "g")
        .str.replace("-", "ー")
    )

    # change1薬品名の文字、包装部分を削除していく
    df["change1薬品名"] = df["medi薬品名"].str.extract(r"(.*)PTP", expand=False)  # PTPの処理
    df["name_flag"] = df[
        "change1薬品名"
    ].isnull()  # 変換できなかったデータの確認 ※name_flag=Falseが医薬品名変更終了

    # 『バラ』の処理
    df["change2薬品名"] = df["medi薬品名"].str.extract(r"(.*)バラ", expand=False)  # PTPの処理
    # 変更した薬品名をchange1薬品名に導入する　（一つの関数にまとめらなかった・・）
    df["導入_flag"] = df["medi薬品名"].str.contains("バラ")  # 導入カラムを作成
    query_str = "導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "change1薬品名"] = df["change2薬品名"]  # 変換した医薬品名をインポート
    df.loc[
        df_subset.index, "name_flag"
    ] = False  # 引き渡した医薬品名はfalseに変換　※シアノコバラミンが誤変換※バラシクロビルはNanになる

    # 一覧単位薬価とメディセオ単位薬価の相違をなくす
    # メジコン配合シロップ　スチックゼノール　プロペト　の単位薬価が10倍
    df["単価調整_flag"] = df["medi薬品名"].str.contains("メジコン配合シロップ|スチックゼノール|プロペト")
    query_str = "単価調整_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "medi単価"] = df["medi単価"] / 10  # 単位薬価の調整

    # medi_check薬品名を作成する
    # 『「」』の処理
    def change_gene(x):
        if x["name_flag"] == 1:
            return x["medi薬品名"].split("」")[0] + "」"  # 「」の後ろ文字がいらない
        else:
            pass

    df["change2薬品名"] = df.apply(change_gene, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした
    df["name導入_flag"] = df["change2薬品名"].str.contains("「", "」")  # 医薬品に「」をもつ導入カラムを作成
    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "change1薬品名"] = df["change2薬品名"]  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = False  # 引き渡した医薬品名はfalseに変換

    # 『%』の処理
    def change_percent(x):
        if x["name_flag"] == 1:
            return x["medi薬品名"].split("%")[0]
        else:
            pass

    df["change2薬品名"] = df.apply(change_percent, axis=1)  # ジェネリック医薬品名を変換してchange2医薬品名にした

    df["name導入_flag"] = df["medi薬品名"].str.contains("%")  # 医薬品に"%"をもつ導入カラムを作成

    # 『「」』の処理済は"name導入_flag　をFalseにする
    # name導入_flag 変換関数
    def name_flag_change(x):
        if x["name_flag"] == False:
            x["name導入_flag"] = False

        else:
            x["name導入_flag"] = x["name導入_flag"]
        return x["name導入_flag"]

    df["name導入_flag"] = df.apply(name_flag_change, axis=1)

    query_str = "name導入_flag == 1"
    df_subset = df.query(query_str)
    df.loc[df_subset.index, "change1薬品名"] = df["change2薬品名"] + "%"  # 変換した医薬品名をインポート
    df.loc[df_subset.index, "name_flag"] = False  # 引き渡した医薬品名はfalseに変換
    # check医薬品名未変換している　「漢方」「ヒート」
    df.rename(columns={"change1薬品名": "check_medi薬品名"}, inplace=True)

    # df_select = df[["JANコード","medi薬品名","check_medi薬品名","medi単価"]]
    df = df[["JANコード", "medi薬品名", "check_medi薬品名", "medi単価"]]

    return df


# 一覧の前処理
def cleansing_ichiran(df):
    df.columns = [
        "load薬品名",
        "棚番",
        "薬価",
        "レセコン単価",
        "在庫数",
        "単位",
        "JANコード",
    ]  # カラム名変更（念のため）
    # 正規表現一覧
    pattan_kakko = "(\(.*\))"
    pattan_split_jan = "(\d+)\;"

    df["包装"] = df["load薬品名"].str.extract(pattan_kakko, expand=False)  # （）内にある包装を抜き出す
    df["check薬品名"] = df["load薬品名"].str.extract(
        r"(.*)\(", expand=False
    )  # 薬品名を他ファイルでもチェックできるように整形
    df["check薬品名"] = df["check薬品名"].apply(
        mojimoji.zen_to_han, kana=False
    )  # 数字と英語は半角、カナ文字と漢字は全角
    df.drop("load薬品名", axis=1, inplace=True)  # load薬品名の削除

    # JANコードの整理
    # dropna()が使えなかったので他の方法で
    df.fillna({"JANコード": "0"}, inplace=True)  # JANコードがない医薬品名は0にする
    rows_to_drop = df.index[df["JANコード"] == "0"]  # 繰り返しの処理が必要？
    df.drop(rows_to_drop, inplace=True)

    jan_list = df["JANコード"].str.split("(\d+)\;", expand=True)

    # JANコードを最大3個まで取り出す
    jan_list = jan_list.rename(columns={1: "JANコード1", 3: "JANコード2", 5: "JANコード3"})
    jan_list_join = jan_list[["JANコード1", "JANコード2", "JANコード3"]]
    df = pd.concat([df, jan_list_join], axis=1)
    df.fillna({"JANコード2": "1"}, inplace=True)  # Nanを1にする
    df.fillna({"JANコード3": "1"}, inplace=True)  # Nanを1にする

    df.columns = [
        "棚番",
        "薬価",
        "レセコン単価",
        "在庫数",
        "単位",
        "JANコード",
        "包装",
        "check薬品名",
        "JANコード1",
        "JANコード2",
        "JANコード3",
    ]

    # df_select = df[["JANコード1","JANコード2","JANコード3","check薬品名","棚番","在庫数","薬価","レセコン単価"]]
    df = df[
        ["JANコード1", "JANコード2", "JANコード3", "check薬品名", "単位", "棚番", "在庫数", "薬価", "レセコン単価"]
    ]
    jan1 = df["JANコード1"]
    jan2 = df["JANコード2"]
    jan3 = df["JANコード3"]
    df["JANコード1"] = pd.Series(jan1, dtype="int64")
    df["JANコード2"] = pd.Series(jan2, dtype="int64")
    df["JANコード3"] = pd.Series(jan3, dtype="int64")

    return df


def read_upload_file(
    file, func, orosigyousha, skipfooter=0, skiprows=None, usecols=None
):
    if file:
        df = pd.read_excel(
            file, skipfooter=skipfooter, skiprows=skiprows, usecols=usecols
        )
        df_clean = func(df).replace(
            "", float("nan")
        )  # .drop_duplicates()  # 空文字をnanにするreplace("", float("nan"))#drop_duplicates()重複文字を消さないで行う
    else:
        if orosigyousha == "suzu":
            df = pd.DataFrame(
                {
                    "JANコード": [999999999999],
                    "load薬品名": ["zzzzzzz"],
                    "load包装": ["yyyy11"],
                    "load納入価": [9999999],
                }
            )
            df_clean = func(df).replace(
                "", float("nan")
            )  # .drop_duplicates()  # 空文字をnanにするreplace("", float("nan"))#drop_duplicates()重複文字を消さないで行う

        else:
            df_clean = pd.DataFrame()

    return df_clean


def split_ok_ng(df, check_col, ok_col, ng_col):
    if len(df):
        df_ok = df[df[check_col].notna()][ok_col]
        df_ng = df[df[check_col].isna()][ng_col]
    else:
        df_ok = pd.DataFrame()
        df_ng = pd.DataFrame()
    return df_ok, df_ng


# 　卸_flagに企業名を代入する関数
def change_oroshi_name(x):
    if x["卸_flag"] == 1:
        x["卸_flag"] = "中北"
    elif x["卸_flag"] == 2:
        x["卸_flag"] = "メディセオ"
    elif x["卸_flag"] == 3:
        x["卸_flag"] = "スズケン"
    else:
        pass

    return x["卸_flag"]


if check_password():
    st.subheader("おろしアプリ")
    suzu_upload = st.file_uploader("スズケン", type={"xlsx"})
    naka_upload = st.file_uploader("中北薬品", type={"xlsx"})
    medi_upload = st.file_uploader("メディセオ", type={"xlsx"})
    ichiran_upload = st.file_uploader("在庫一覧", type={"xlsx"})

    if not st.session_state.get("button", False):
        push_button = st.button("代入スタート")
    else:
        push_button = True
    if push_button:
        st.session_state.button = push_button
        df_suzu_clean = read_upload_file(
            suzu_upload, cleansing_suzu, "suzu", skipfooter=1, usecols=[0, 2, 3, 7]
        )
        df_medi_clean = read_upload_file(
            medi_upload, cleansing_medi, "medi", skiprows=2, usecols=[0, 2, 3, 8]
        )

        df_naka_clean = read_upload_file(
            naka_upload, cleansing_naka, "naka", usecols=[1, 2, 3, 5]
        )

        df_ichiran_clean = read_upload_file(
            ichiran_upload,
            cleansing_ichiran,
            "ichiran",
            usecols=[3, 6, 7, 8, 9, 11, 17],
        )

        # df_ichiran_cleanに単位納入価を付け終えた「決定単価」と「完了_flag」のカラムを作成
        df_ichiran_clean["決定単価"] = 0
        df_ichiran_clean["決定単価"] = df_ichiran_clean["決定単価"].astype("float64")
        df_ichiran_clean["卸_flag"] = 0  # 採用卸がわかるよう「卸_flag」を追加
        df_ichiran_clean["決定薬品名"] = "該当なし"

        # 中北の処理
        # 中北のJANコード一致で単位納入価を付ける
        # print(df_naka_clean["JANコード"].duplicated().sum())#念のため、JANコードの重複確認
        df_naka_clean.drop_duplicates(
            subset="JANコード", keep="first", inplace=True
        )  # JANコード重複を消す
        # 中北内のJANコード重複を消した後、外部結合でくっつける
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード1": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_naka_clean, how="left", on="JANコード"
        )

        # 単位納入価が付けらた医薬品の「完了_flag」をture　いらないカラムを削除
        query_str = "naka単価 > 0"
        df_subset = df_ichiran_clean.query(query_str)
        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 1  # 卸中北で補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "naka薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "naka単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード1"})

        # JANコード2を外部結合でくっつける
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード2": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_naka_clean, how="left", on="JANコード"
        )
        # if文がつくれなかった・・
        query_str = "naka単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 1  # 卸中北で補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "naka薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "naka単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード2"})

        # JANコード3を外部結合でくっつける
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード3": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_naka_clean, how="left", on="JANコード"
        )

        # if文がつくれなかった・・
        query_str = "naka単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)
        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 1  # 卸中北で補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "naka薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "naka単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード3"})

        # メディセオの処理
        # メディセオのJANコード一致で単位納入価を付ける
        # print(df_read_medu["JANコード"].duplicated().sum())#念のため、JANコードの重複確認
        df_medi_clean.drop_duplicates(
            subset="JANコード", keep="first", inplace=True
        )  # JANコード重複を消す

        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード1": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_medi_clean, how="left", on="JANコード"
        )

        # 重複リスト『dupli_naka_medi_list1』を作成
        # if文がつくれなかった・・
        dupli_str = "medi単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_medi_list1 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_naka_medi_list1 = dupli_naka_medi_list1.iloc[:, [5, 9, 10, 11, 12, 14]]

        # if文がつくれなかった・・
        query_str = "medi単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 2  # 卸メディセオで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "medi薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "medi単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード1"})

        # メディセオのJANコード2の処理
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード2": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_medi_clean, how="left", on="JANコード"
        )
        # 重複リスト『dupli_naka_medi_list2』を作成
        # if文がつくれなかった・・
        dupli_str = "medi単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_medi_list2 = df_dupli.query(dupli_str)
        dupli_naka_medi_list2 = dupli_naka_medi_list2.iloc[:, [5, 9, 10, 11, 12, 14]]
        # if文がつくれなかった・・
        query_str = "medi単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 2  # 卸メディセオで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "medi薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "medi単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード2"})

        # メディセオのJANコード3の処理
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード3": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_medi_clean, how="left", on="JANコード"
        )
        # 重複リスト『dupli_naka_medi_list3』を作成
        # if文がつくれなかった・・
        dupli_str = "medi単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_medi_list3 = df_dupli.query(dupli_str)
        dupli_naka_medi_list3 = dupli_naka_medi_list3.iloc[:, [5, 9, 10, 11, 12, 14]]
        # if文がつくれなかった・・
        query_str = "medi単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 2  # 卸メディセオで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "medi薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "medi単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード3"})

        # 重複リストをくっつける
        dupli_naka_medi_list = pd.concat(
            [dupli_naka_medi_list1, dupli_naka_medi_list2, dupli_naka_medi_list3]
        )
        dupli_naka_medi_list.drop_duplicates(subset="棚番", inplace=True)

        # スズケンの処理
        # スズケンのJANコード一致で単位納入価を付ける
        # print(df_read_medu["JANコード"].duplicated().sum())#念のため、JANコードの重複確認
        df_suzu_clean.drop_duplicates(
            subset="JANコード", keep="first", inplace=True
        )  # JANコード重複を消す

        # スズケンのJANコード1の処理
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード1": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_suzu_clean, how="left", on="JANコード"
        )
        # if文がつくれなかった・・
        query_str = "suzu単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        # 重複リスト『dupli_naka_suzu_list1』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_suzu_list1 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_naka_suzu_list1 = dupli_naka_suzu_list1.iloc[:, [5, 9, 10, 11, 12, 14]]

        # 重複リスト『dupli_medi_suzu_list1』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 2"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_medi_suzu_list1 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_medi_suzu_list1 = dupli_medi_suzu_list1.iloc[:, [5, 9, 10, 11, 12, 14]]

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 3  # 卸スズケンで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "suzu薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "suzu単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード1"})

        # スズケンのJANコード2の処理
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード2": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_suzu_clean, how="left", on="JANコード"
        )
        # if文がつくれなかった・・
        query_str = "suzu単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        # 重複リスト『dupli_naka_suzu_list2』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_suzu_list2 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_naka_suzu_list2 = dupli_naka_suzu_list2.iloc[:, [5, 9, 10, 11, 12, 14]]

        # 重複リスト『dupli_medi_suzu_list2』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 2"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_medi_suzu_list2 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_medi_suzu_list2 = dupli_medi_suzu_list2.iloc[:, [5, 9, 10, 11, 12, 14]]

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 3  # 卸スズケンで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "suzu薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "suzu単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード2"})

        # スズケンのJANコード3の処理
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード3": "JANコード"})
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_suzu_clean, how="left", on="JANコード"
        )
        # if文がつくれなかった・・
        query_str = "suzu単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        # 重複リスト『dupli_naka_suzu_list3』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_naka_suzu_list3 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_naka_suzu_list3 = dupli_naka_suzu_list3.iloc[:, [5, 9, 10, 11, 12, 14]]

        # 重複リスト『dupli_medi_suzu_list2』を作成
        # if文がつくれなかった・・
        dupli_str = "suzu単価 > 0"
        dupli_sub = "卸_flag == 2"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_medi_suzu_list3 = df_dupli.query(dupli_str)
        # いらないカラムをおとす
        dupli_medi_suzu_list3 = dupli_medi_suzu_list3.iloc[:, [5, 9, 10, 11, 12, 14]]

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 3  # 卸スズケンで補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "suzu薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "suzu単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(columns={"JANコード": "JANコード3"})

        # 重複リストをくっつける
        dupli_naka_suzu_list = pd.concat(
            [dupli_naka_suzu_list1, dupli_naka_suzu_list2, dupli_naka_suzu_list3]
        )
        dupli_naka_suzu_list.drop_duplicates(subset="棚番", inplace=True)

        dupli_medi_suzu_list = pd.concat(
            [dupli_medi_suzu_list1, dupli_medi_suzu_list2, dupli_medi_suzu_list3]
        )
        dupli_medi_suzu_list.drop_duplicates(subset="棚番", inplace=True)

        # 101個がうまってない
        # df_ichiran_clean.to_csv('tana_input.csv',
        # columns=["check薬品名","棚番","在庫数","決定薬品名","決定単価","卸_flag","薬価","レセコン単価"], encoding=("utf-8-sig"))

        # check_naka薬品名　で代入させる　スズケンは全店舗なので行わない
        # 中北のcheck_naka薬品名の処理

        df_ichiran_clean = df_ichiran_clean.rename(
            columns={"check薬品名": "check_naka薬品名"}
        )
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_naka_clean, how="left", on="check_naka薬品名"
        )

        # if文がつくれなかった・・
        query_str = "naka単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 1  # 卸中北で補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "naka薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "naka単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(
            columns={"check_naka薬品名": "check薬品名"}
        )

        # メディセオのcheck_medi薬品名の処理
        df_ichiran_clean = df_ichiran_clean.rename(
            columns={"check薬品名": "check_medi薬品名"}
        )
        df_ichiran_clean = pd.merge(
            df_ichiran_clean, df_medi_clean, how="left", on="check_medi薬品名"
        )
        # 重複リスト『dupli_housou_medi_list』を作成 包装違いの重複
        # if文がつくれなかった・・
        dupli_str = "medi単価 > 0"
        dupli_sub = "卸_flag == 1"
        df_dupli = df_ichiran_clean.query(dupli_sub)
        dupli_housou_medi_list = df_dupli.query(dupli_str)
        dupli_housou_medi_list = dupli_housou_medi_list.iloc[:, [5, 9, 10, 11, 12, 14]]

        # if文がつくれなかった・・
        query_str = "medi単価 > 0"
        query_sub = "卸_flag == 0"
        df_sub = df_ichiran_clean.query(query_sub)
        df_subset = df_sub.query(query_str)

        df_ichiran_clean.loc[df_subset.index, "卸_flag"] = 2  # 卸中北で補えるflag
        df_ichiran_clean.loc[df_subset.index, "決定薬品名"] = df_ichiran_clean.loc[
            df_subset.index, "medi薬品名"
        ]  # 薬品名代入
        df_ichiran_clean.loc[df_subset.index, "決定単価"] = df_ichiran_clean.loc[
            df_subset.index, "medi単価"
        ]  # 決定単価を代入
        # いらないカラムをおとす JANコードを戻す
        df_ichiran_clean = df_ichiran_clean.iloc[
            :, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ]
        df_ichiran_clean = df_ichiran_clean.rename(
            columns={"check_medi薬品名": "check薬品名"}
        )

        # check_nameで4個埋まる
        # 決定単価の重複を消す
        df_ichiran_clean.drop_duplicates(subset="check薬品名", keep="last", inplace=True)

        #'tana_input.csv'に必要カラムを追加する
        difference = df_ichiran_clean["薬価"] - df_ichiran_clean["決定単価"]
        df_ichiran_clean["薬価差率"] = difference / df_ichiran_clean["薬価"] * 100
        df_ichiran_clean["誤差"] = 0
        df_ichiran_clean["誤差"] = df_ichiran_clean["誤差"].astype(float)

        # 卸名に変換
        df_ichiran_clean["卸_flag"] = df_ichiran_clean.apply(change_oroshi_name, axis=1)

        # dupli_listの卸_flagは未変換の処理
        dupli_naka_medi_list["卸_flag"] = dupli_naka_medi_list.apply(
            change_oroshi_name, axis=1
        )
        dupli_naka_suzu_list["卸_flag"] = dupli_naka_suzu_list.apply(
            change_oroshi_name, axis=1
        )
        dupli_medi_suzu_list["卸_flag"] = dupli_medi_suzu_list.apply(
            change_oroshi_name, axis=1
        )
        dupli_housou_medi_list["卸_flag"] = dupli_housou_medi_list.apply(
            change_oroshi_name, axis=1
        )

        df_ichiran_clean_select = df_ichiran_clean[
            [
                "check薬品名",
                "単位",
                "在庫数",
                "誤差",
                "棚番",
                "薬価",
                "決定単価",
                "薬価差率",
                "卸_flag",
                "決定薬品名",
                "レセコン単価",
            ]
        ]

        # change1薬品名にはnanがあるので注意
        st.download_button(
            label="入力用CSV",
            data=df_ichiran_clean_select.to_csv().encode("utf-8-sig"),
            file_name="tana_input.csv",
            mime="text/csv",
        )

        # 重複確認をあとづけ
        dupli_naka_medi_list_select = dupli_naka_medi_list[
            ["棚番", "決定単価", "卸_flag", "決定薬品名", "medi薬品名", "medi単価"]
        ]
        st.download_button(
            label="中北とメディセオの重複結果CSV",
            data=dupli_naka_medi_list_select.to_csv().encode("utf-8-sig"),
            file_name="中北とメディセオ重複の結果.csv",
            mime="text/csv",
        )

        dupli_naka_suzu_list_select = dupli_naka_suzu_list[
            ["棚番", "決定単価", "卸_flag", "決定薬品名", "suzu薬品名", "suzu単価"]
        ]
        st.download_button(
            label="中北とスズケンの重複結果CSV",
            data=dupli_naka_suzu_list_select.to_csv().encode("utf-8-sig"),
            file_name="中北とスズケン重複の結果.csv",
            mime="text/csv",
        )

        dupli_medi_suzu_list_select = dupli_medi_suzu_list[
            ["棚番", "決定単価", "卸_flag", "決定薬品名", "suzu薬品名", "suzu単価"]
        ]
        st.download_button(
            label="メディセオとスズケンの重複結果CSV",
            data=dupli_medi_suzu_list_select.to_csv().encode("utf-8-sig"),
            file_name="メディセオとスズケン重複の結果.csv",
            mime="text/csv",
        )

        dupli_housou_medi_list_select = dupli_housou_medi_list[
            ["棚番", "決定単価", "卸_flag", "決定薬品名", "JANコード", "medi単価"]
        ]
        st.download_button(
            label="中北とメディセオ包装が重複の結果CSV",
            data=dupli_housou_medi_list_select.to_csv().encode("utf-8-sig"),
            file_name="中北とメディセオ包装が重複の結果.csv",
            mime="text/csv",
        )

    st.subheader("卸データ作成")
    input_upload = st.file_uploader("作成するデータ", type={"xlsx"})

    if not st.session_state.get("button2", False):
        push_button2 = st.button("作成スタート")
    else:
        push_button2 = True
    if push_button2:
        st.session_state.button2 = push_button2

        df_input = pd.read_excel(
            input_upload, usecols=[1, 2, 3, 4, 5, 6, 7]
        )  # index_col=0でUnnamed: 0がなくなる
        # カラム名の変更
        df_input.columns = [
            "薬品名",
            "単位",
            "理論値",
            "誤差",
            "棚番",
            "薬価",
            "納入単価",
        ]  # カラム名変更（念のため）

        # 棚番のNanを置き換える
        df_input["棚番"] = df_input["棚番"].fillna("　")
        # 棚番から頭文字1字を抽出
        pattern = "^."

        def change_initials(x):
            res = re.match(pattern, x["棚番"])
            x["棚"] = res.group()

            return x["棚"]

        df_input["棚"] = df_input.apply(change_initials, axis=1)

        # 必要カラムの追加
        df_input["在庫数"] = 0
        df_input["在庫数"] = df_input["在庫数"].astype(float)
        # 『在庫数』カラムの追加
        df_input["在庫数"] = df_input["理論値"] + df_input["誤差"]
        difference = df_input["薬価"] - df_input["納入単価"]
        df_input["対薬価率"] = difference / df_input["薬価"] * 100
        df_input["在庫金額"] = df_input["在庫数"] * df_input["納入単価"]
        df_input["誤差金額"] = df_input["誤差"] * df_input["納入単価"]
        df_input["誤差金額合計"] = df_input["誤差金額"].abs()

        # ソート
        df_input = df_input.sort_values(by=("棚番"), ascending=True)

        # df出力の処理
        # 棚ごとの合計値　棚名称　数　在庫金額　誤差金額　誤差率
        tana_len = df_input.groupby("棚").size()

        tana_total = df_input.groupby("棚", as_index=True).apply(
            lambda d: (d["在庫金額"]).sum()
        )
        tana_totalerror = df_input.groupby("棚", as_index=True).apply(
            lambda d: (d["誤差金額"]).sum()
        )
        tana_totalerror_abs = df_input.groupby("棚", as_index=True).apply(
            lambda d: (d["誤差金額合計"]).sum()
        )
        df_tana_list = pd.DataFrame(tana_len, columns=["医薬品数"])
        df_tana_list_result = pd.concat(
            [df_tana_list, tana_total, tana_totalerror, tana_totalerror_abs], axis=1
        )
        df_tana_list_result.columns = [
            "医薬品数",
            "在庫金額合計",
            "誤差金額合計",
            "絶対値合計",
        ]  # カラム名変更（念のため）
        df_tana_list_result["誤差率"] = (
            df_tana_list_result["絶対値合計"] / df_tana_list_result["在庫金額合計"] * 100
        )

        df_input_select = df_input[
            [
                "棚",
                "棚番",
                "薬品名",
                "単位",
                "理論値",
                "在庫数",
                "誤差",
                "納入単価",
                "薬価",
                "対薬価率",
                "在庫金額",
                "誤差金額",
            ]
        ]
        st.download_button(
            label="棚おろしリストCSV",
            data=df_input_select.to_csv(index=False).encode("utf-8-sig"),
            file_name="tana_list.csv",
            mime="text/csv",
        )

        st.download_button(
            label="棚合計の結果CSV",
            data=df_tana_list_result.to_csv().encode("utf-8-sig"),
            file_name="棚合計の結果.csv",
            mime="text/csv",
        )

        # change1薬品名にはnanがあるので注意

        st.subheader("合計の結果")
        st.dataframe(df_tana_list_result)
