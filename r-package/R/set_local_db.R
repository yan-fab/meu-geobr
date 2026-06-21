############# Local database management for geobr

# Regex to parse geobr Parquet file names
# Pattern: {geography}_{year}_{type}.parquet
# e.g. municipalities_2022_simplified.parquet
.geobr_filename_re <- "^(.+)_(\\d{4})_(simplified|original)\\.parquet$"



#' Configure a local directory as the geobr data source
#'
#' @description
#' After calling `set_local_db()`, all `read_*()` functions will first look for
#' the requested dataset in the specified directory before attempting any
#' network download.
#'
#' Files in the local directory must follow the geobr naming convention:
#'
#' - `{geography}_{year}_simplified.parquet`  (for `simplified = TRUE`)
#' - `{geography}_{year}_original.parquet`    (for `simplified = FALSE`)
#'
#' @param path `character`. Path to a directory containing geobr Parquet files.
#'
#' @return Invisibly returns the configured path (as a `character` string).
#'
#' @export
#'
#' @examples \dontrun{
#' set_local_db("/data/geobr/")
#' get_local_db()
#' list_local_datasets()
#' mun <- read_municipality(year = 2022)   # uses local file, no download
#' clear_local_db()
#' }
set_local_db <- function(path) {
  checkmate::assert_string(path, min.chars = 1)

  p <- normalizePath(path, mustWork = FALSE)

  if (!dir.exists(p)) {
    cli::cli_abort(c(
      "Path does not exist: {.path {p}}",
      "i" = "Please provide a valid directory containing geobr Parquet files."
    ))
  }

  geobr_env$local_db <- p
  cli::cli_alert_success("Local geobr database set to: {.path {p}}")
  invisible(p)
}


#' Return the currently configured local database path
#'
#' @description
#' Returns the directory path set via [set_local_db()], or `NULL` if no local
#' database has been configured.
#'
#' @return `character` path, or `NULL`.
#'
#' @export
#'
#' @examples \dontrun{
#' set_local_db("/data/geobr/")
#' get_local_db()
#' }
get_local_db <- function() {
  geobr_env$local_db
}


#' Remove the local database configuration
#'
#' @description
#' Clears the path set by [set_local_db()]. After calling this function,
#' `read_*()` functions resume downloading data from the geobr servers.
#'
#' @return Invisibly returns `NULL`.
#'
#' @export
#'
#' @examples \dontrun{
#' clear_local_db()
#' }
clear_local_db <- function() {
  geobr_env$local_db <- NULL
  cli::cli_alert_info("Local geobr database cleared. Downloads will resume from the network.")
  invisible(NULL)
}


#' List datasets available in the configured local directory
#'
#' @description
#' Scans the local directory configured via [set_local_db()] and returns a
#' `data.frame` describing every recognised geobr Parquet file found there.
#'
#' Files are recognised when they follow the naming convention:
#' `{geography}_{year}_simplified.parquet` or
#' `{geography}_{year}_original.parquet`.
#'
#' @return A `data.frame` with columns `geography`, `year`, `simplified`, and
#'   `path`. Returns an empty `data.frame` if no local database is configured
#'   or no matching files are found.
#'
#' @export
#'
#' @examples \dontrun{
#' set_local_db("/data/geobr/")
#' list_local_datasets()
#' }
list_local_datasets <- function() {
  empty <- data.frame(
    geography  = character(),
    year       = integer(),
    simplified = logical(),
    path       = character(),
    stringsAsFactors = FALSE
  )

  if (is.null(geobr_env$local_db)) {
    cli::cli_alert_info(
      "No local database configured. Use {.fn set_local_db} first."
    )
    return(invisible(empty))
  }

  db_path <- geobr_env$local_db

  if (!dir.exists(db_path)) {
    cli::cli_abort(c(
      "Configured local database path no longer exists: {.path {db_path}}",
      "i" = "Update it with {.fn set_local_db} or call {.fn clear_local_db}."
    ))
  }

  parquet_files <- list.files(db_path, pattern = "\\.parquet$", full.names = TRUE)

  if (length(parquet_files) == 0) {
    cli::cli_alert_warning(
      "No Parquet files found in: {.path {db_path}}"
    )
    return(invisible(empty))
  }

  rows <- lapply(parquet_files, function(fp) {
    fname <- basename(fp)
    m <- regmatches(fname, regexec(.geobr_filename_re, fname))[[1]]
    if (length(m) == 0) return(NULL)
    list(
      geography  = m[2],
      year       = as.integer(m[3]),
      simplified = m[4] == "simplified",
      path       = fp
    )
  })

  rows <- rows[!sapply(rows, is.null)]

  if (length(rows) == 0) {
    cli::cli_alert_warning(c(
      "No geobr Parquet files with valid names found in: {.path {db_path}}",
      "i" = "Files must follow: {{geography}}_{{year}}_simplified.parquet"
    ))
    return(invisible(empty))
  }

  result <- do.call(rbind, lapply(rows, as.data.frame, stringsAsFactors = FALSE))
  result$year <- as.integer(result$year)
  result$simplified <- as.logical(result$simplified)
  rownames(result) <- NULL
  return(result)
}


#' Resolve the local Parquet path for a requested dataset (internal)
#'
#' @param geography `character`. The geobr geography identifier.
#' @param year `integer`. The requested year, or `NULL` for the latest.
#' @param simplified `logical`. Whether simplified geometry is requested.
#'
#' @return Full path to the local Parquet file as `character`, or `NULL` if
#'   not found.
#'
#' @keywords internal
resolve_local_path <- function(geography, year = NULL, simplified = TRUE) { # nocov start
  db_path <- geobr_env$local_db

  if (is.null(db_path) || !dir.exists(db_path)) {
    return(NULL)
  }

  suffix <- if (isTRUE(simplified)) "simplified" else "original"

  # Direct match when year is specified
  if (!is.null(year)) {
    candidate <- file.path(db_path, paste0(geography, "_", year, "_", suffix, ".parquet"))
    if (file.exists(candidate) && file.info(candidate)$size > 0) {
      return(candidate)
    }
    return(NULL)
  }

  # When year is NULL: find the latest year available locally
  pattern <- paste0("^", geography, "_(\\d{4})_", suffix, "\\.parquet$")
  files <- list.files(db_path, pattern = pattern, full.names = TRUE)

  if (length(files) == 0) {
    return(NULL)
  }

  # Extract years and return the file with the latest year
  years <- as.integer(
    regmatches(basename(files), regexpr("\\d{4}", basename(files)))
  )
  return(files[which.max(years)])
} # nocov end
