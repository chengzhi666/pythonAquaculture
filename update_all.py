from runner import run_from_config


def update_all():
    # run_from_config 内部已经会打印 “采集统计 + 全部采集完成”
    run_from_config(
        config_path="config/sites.json",
        overrides={},
        save_to_db=True,
    )


if __name__ == "__main__":
    update_all()
