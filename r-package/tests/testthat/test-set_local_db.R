test_that("set_local_db() rejects non-existent paths", {
  expect_error(
    set_local_db("/caminho/que/nao/existe/xyz"),
    regexp = "does not exist|Path does not exist"
  )
})

test_that("set_local_db() rejects file paths (not directories)", {
  tmp <- tempfile(fileext = ".parquet")
  writeBin(as.raw(c(0x50, 0x41, 0x52, 0x31)), tmp) # PAR1 magic bytes
  on.exit(unlink(tmp))
  expect_error(set_local_db(tmp))
})

test_that("set_local_db() accepts a valid directory", {
  tmp_dir <- tempdir()
  expect_no_error(set_local_db(tmp_dir))
  expect_equal(get_local_db(), normalizePath(tmp_dir))
  clear_local_db()
})

test_that("get_local_db() returns NULL when not set", {
  clear_local_db()
  expect_null(get_local_db())
})

test_that("get_local_db() returns path after set_local_db()", {
  tmp_dir <- tempdir()
  set_local_db(tmp_dir)
  expect_equal(get_local_db(), normalizePath(tmp_dir))
  clear_local_db()
})

test_that("clear_local_db() removes the configured path", {
  set_local_db(tempdir())
  clear_local_db()
  expect_null(get_local_db())
})

test_that("clear_local_db() does not error when already NULL", {
  clear_local_db()
  expect_no_error(clear_local_db())
  expect_null(get_local_db())
})

test_that("list_local_datasets() returns empty data.frame when not set", {
  clear_local_db()
  result <- list_local_datasets()
  expect_s3_class(result, "data.frame")
  expect_equal(nrow(result), 0)
  expect_named(result, c("geography", "year", "simplified", "path"))
})

test_that("list_local_datasets() parses valid geobr Parquet files", {
  tmp_dir <- tempfile()
  dir.create(tmp_dir)
  on.exit(unlink(tmp_dir, recursive = TRUE))

  # Create fake Parquet files (non-empty)
  valid_files <- c(
    "municipalities_2022_simplified.parquet",
    "states_2020_original.parquet",
    "biomes_2019_simplified.parquet"
  )
  for (f in valid_files) {
    writeBin(charToRaw("PAR1fake"), file.path(tmp_dir, f))
  }
  # Invalid files that should be ignored
  writeBin(charToRaw("text"), file.path(tmp_dir, "readme.txt"))
  writeBin(charToRaw("PAR1fake"), file.path(tmp_dir, "bad_name.parquet"))

  set_local_db(tmp_dir)
  result <- list_local_datasets()
  clear_local_db()

  expect_equal(nrow(result), 3)
  expect_setequal(result$geography, c("municipalities", "states", "biomes"))
  expect_equal(result$year[result$geography == "municipalities"], 2022L)
  expect_true(result$simplified[result$geography == "municipalities"])
  expect_false(result$simplified[result$geography == "states"])
})

test_that("list_local_datasets() errors when configured dir disappears", {
  tmp_dir <- tempfile()
  dir.create(tmp_dir)

  set_local_db(tmp_dir)
  unlink(tmp_dir, recursive = TRUE)

  expect_error(list_local_datasets())
  clear_local_db()
})

test_that("resolve_local_path() returns NULL when no local db configured", {
  clear_local_db()
  result <- resolve_local_path("municipalities", 2022, simplified = TRUE)
  expect_null(result)
})

test_that("resolve_local_path() finds existing simplified file", {
  tmp_dir <- tempfile()
  dir.create(tmp_dir)
  on.exit(unlink(tmp_dir, recursive = TRUE))

  fname <- "municipalities_2022_simplified.parquet"
  writeBin(charToRaw("PAR1fake"), file.path(tmp_dir, fname))

  set_local_db(tmp_dir)
  result <- resolve_local_path("municipalities", 2022, simplified = TRUE)
  clear_local_db()

  expect_false(is.null(result))
  expect_true(grepl(fname, result))
})

test_that("resolve_local_path() returns NULL for missing year", {
  tmp_dir <- tempfile()
  dir.create(tmp_dir)
  on.exit(unlink(tmp_dir, recursive = TRUE))

  writeBin(charToRaw("PAR1fake"),
           file.path(tmp_dir, "municipalities_2022_simplified.parquet"))

  set_local_db(tmp_dir)
  result <- resolve_local_path("municipalities", 1990, simplified = TRUE)
  clear_local_db()

  expect_null(result)
})

test_that("resolve_local_path() returns latest year when year=NULL", {
  tmp_dir <- tempfile()
  dir.create(tmp_dir)
  on.exit(unlink(tmp_dir, recursive = TRUE))

  writeBin(charToRaw("PAR1fake"),
           file.path(tmp_dir, "municipalities_2020_simplified.parquet"))
  writeBin(charToRaw("PAR1fake"),
           file.path(tmp_dir, "municipalities_2022_simplified.parquet"))

  set_local_db(tmp_dir)
  result <- resolve_local_path("municipalities", year = NULL, simplified = TRUE)
  clear_local_db()

  expect_false(is.null(result))
  expect_true(grepl("2022", result))
})
