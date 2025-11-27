# 車両データを活用した子ども向け交通安全マップ
## データ処理サーバー
車両から送られてきたセンサー値や画像を処理するサーバーです．

## 構成
- Broker（HiveMQ）から分割された画像を受け取ります．
- YOLO, SAM2を用いて画像にマスキング処理を行います．
- データベースとオブジェクトストレージに，データを保存します．

## 手順
1. このリポジトリをクローンします．
2. .envファイルを作成して，環境変数を書き込んでください．
3. ```pip install -r requirements.txt```で依存関係をインストールします。
4. ```python pipeline.py```コマンドを実行します．

## 環境変数

| 項目                 | 詳細                                                                                               | 
| -------------------- | -------------------------------------------------------------------------------------------------- | 
| SUPABASE_URL         | supabaseのエンドポイントURLを記載します。<br>https://xxx.supabase.coの形式です。                   | 
| SUPABASE_KEY         | supabaseのシークレットキーを記載します。                                                           | 
| R2_ENDPOINT          | Cloudflare R2のエンドポイントURLを記載します。<br>https://xxx.r2.cloudflarestorage.comの形式です。 | 
| R2_ACCESS_KEY        | Cloudflare R2のアクセスキーを記載します。                                                          | 
| R2_ACCESS_KEY_SECRET | Cloudflare R2のシークレットアクセスキーを記載します。   