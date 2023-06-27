"""
Downloads the latest versions of all installed VSCode extensions with cURL. Finds versions that are
compatible with the "code_version" in the script.
"""

import os
import json
import zipfile
import tempfile
import subprocess
import re
import requests
from tqdm import tqdm

override = False             # use this to override the check on whether the compatible_packages json has already been made.
code_version = '1.77.3'      # change this to the version of VScode you are targeting for offline operation.
output_dir = './extensions'  # change this to wherever you want to save out the compatible extension VSIX files.
comparison_operators = {
        "<": -1,
        "<=": -1,
        ">": 1,
        ">=": 1,
        "==": 0
    }

def parse_version_string(version_str) -> tuple:
    """
    Parses a version string to extract the version number in the proper format for comparisons

    Args:
        version_str (str): A version string extracted from the vsce tool's report on a VS code extension package

    Returns:
        tuple: returns a comparison operator as well as the version string if comparison operator is detected,
        otherwise, just returns the unmodified version string with zero 
    """
    if any(op in version_str for op in comparison_operators):
        operator, version = re.match(r"([<>=]+)?(.+)", version_str).groups()
        return (comparison_operators.get(operator, 0), version)
    return (0, version_str)

def get_compatible_version(extension) -> str:
    """
    Retrieves latest available version of a VSCode extension using the 'vsce' command-line tool.

    Args:
        extension (str): The full name of the extension in the format of {publisher}.{package}.

    Returns:
        latest_compatible_package_version (string): A string containing the latest compatible version 
    """
    command = f"vsce show {extension} --json"
    output = subprocess.check_output(command, shell=True)
    data = json.loads(output)
    versions = [version["version"] for version in data["versions"]]
    
    latest_compatible_package_version = extract_compatible_vscode_version(extension, versions)

    return latest_compatible_package_version

def extract_compatible_vscode_version(extension, versions) -> str:
    """
    Extracts the compatible VSCode version for the extension.

    Args:
        extension (str): The full name of the extension in the format of {publisher}.{package}.
        versions (list): List of available versions for the extension.

    Returns:
        str: The compatible VSCode version, or None if there isn't one.
    """
    compatible_versions = None
    for version in tqdm(versions, desc=f"Searching through {extension}'s versions for one compatible with VScode version {code_version}", total=len(versions)):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_url = get_package_url(extension, version)
            package_path = download_package(package_url, temp_dir)
            if package_path:
                package_json = read_package_json(package_path)
                if package_json:
                    engines = package_json.get("engines")
                    if engines and "vscode" in engines:
                        v2 = engines["vscode"].split("^")[-1]
                        if compare_versions(code_version, v2) >= 0:
                            compatible_versions = version
                            break

    return compatible_versions

def get_package_url(extension, version) -> str:
    """
    Constructs the download URL for the extension package.

    Args:
        extension (str): The full name of the extension in the format of {publisher}.{package}.
        version (str): The version of the extension.

    Returns:
        str: The download URL for the extension package.
    """
    publisher, package = extension.split('.')
    return f"https://{publisher}.gallery.vsassets.io/_apis/public/gallery/publisher/{publisher}/extension/{package}/{version}/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage"

def download_package(url, destination_dir) -> str:
    """
    Downloads the extension package from the specified URL and saves it to the destination directory.

    Args:
        url (str): The URL of the extension package.
        destination_dir (str): The directory to save the downloaded package.

    Returns:
        str: The path to the downloaded package file, or None if the download fails.
    """
    response = requests.get(url)
    if response.ok:
        package_path = os.path.join(destination_dir, "extension.vsix")
        with open(package_path, "wb") as file:
            file.write(response.content)
        return package_path
    return None

def read_package_json(package_path) -> dict:
    """
    Reads and parses the package.json file from the extension package.

    Args:
        package_path (str): The path to the extension package.

    Returns:
        dict: The parsed package.json contents as a dictionary, or None if the file cannot be read or parsed.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(package_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        package_json_path = os.path.join(temp_dir, "extension", "package.json")
        try:
            with open(package_json_path, "r") as file:
                package_data = json.load(file)
                return package_data
        except (IOError, json.JSONDecodeError):
            return None

def vsix_url(extension, version) -> str:
    """
    Gets the URL for a .vsix VSCode extension, given the full name
    of the extension in the format of {publish}.{package}
    ex: ms-python.python
    
    Args:
        extension (str): extension name in the {publiser}.{package} format
        version (str): the version number of the package
    """

    publisher, package = extension.split('.')
    return f'https://{publisher}.gallery.vsassets.io/_apis/public/gallery/publisher/{publisher}/extension/{package}/{version}/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage'

def vsix_curl(extension, url, output_dir):
    """
    Builds and returns the cURL command to download a vscode extension 
    to a spexified directory and filename.
    
    Args:
        extension (str): extension (str): extension name in the {publiser}.{package} format
        url (str): valid url of the package extracted from the vsix_url method
        output_dir: a valid directory path to an existing folder where the VSIX file is to be saved
    
    """
    return 'curl {} -o {}/{}.vsix'.format(url, output_dir, extension)

def compare_versions(version1, version2) -> bool:
    """
    Compares two version strings and returns:
    -1 if version1 is less than version2
    0 if version1 is equal to version2
    1 if version1 is greater than version2

    Args:
        version1 (str): First version string to compare.
        version2 (str): Second version string to compare.
        
    Returns: a boolean of whether the version1 is compatible with the version2
    """
    
    v1_comp, v1_parts = parse_version_string(version1)
    v2_comp, v2_parts = parse_version_string(version2)

    v1_parts = [int(part) if part.isdigit() else part for part in v1_parts.split(".")]
    v2_parts = [int(part) if part.isdigit() else part for part in v2_parts.split(".")]

    for i in range(max(len(v1_parts), len(v2_parts))):
        v1 = v1_parts[i] if i < len(v1_parts) else 0
        v2 = v2_parts[i] if i < len(v2_parts) else 0

        if isinstance(v1, int) and isinstance(v2, int):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
        elif isinstance(v1, int):
            return -1
        elif isinstance(v2, int):
            return 1
        elif v1 != v2:
            return -1 if v1 < v2 else 1

    return v1_comp - v2_comp

def check_compat(extension_names):
    """
    Checks if the versions of the VSCode extensions will work with the supplied version of VSCode.
    This method opens each VSIX file directory within the ext_dir, ingests the package.json file as a dictionary, reads the
    ["engines"]["vscode"] key, and then checks whether the supplied vscode_version is less than or equal to this value.
    If it is, then it will store a dictionary with extension information in a list corresponding to the compatible extensions.
    The method returns a list of dictionaries, one for each compatible extension in the ext_dir folder, containing the extension
    name, version, and download URL.

    Args:
        extension_names list(str): a list of all the extension names that you want to determine compatibility for in the {publisher}.{package} format
    """
    compatible_extensions = []

    for extension_name in extension_names:
        compatible_version = get_compatible_version(extension_name)
        extension_url = None   

        if compatible_version:
            extension_url = vsix_url(extension_name, compatible_version)
            
        compatible_extensions.append({
            "name": extension_name,
            "version": compatible_version,
            "url": extension_url
        })

    return compatible_extensions

if __name__ == "__main__":
    # get a list of all currently installed extensions
    extensions = os.popen('code --list-extensions --show-versions').read().splitlines()
    extensions.pop(0)  # on WSL, the first line is not an actual package, it's the header

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    ext_names = []
    for ext in extensions:
        ext_temp, _ = ext.split('@')
        ext_names.append(ext_temp)
        
    # since this process can take a really long time, save out the results after the first time it is run
    if not os.path.exists("./compatible_packages.json") or override == True:
        compatible_packages = check_compat(ext_names)
        with open("compatible_packages.json", "w") as json_file:
            json.dump(compatible_packages, json_file) 
    else:  # NOTE: to re-run the compatibility search, set the override parameter to True!!
        with open("compatible_packages.json", "r") as json_file:
            compatible_packages = json.load(json_file)

    for package in compatible_packages:
        if package["version"]:
            print(f"Downloading latest compatible version of {package['name']} ...")
            url = package["url"]
            command = vsix_curl(package["name"], url, output_dir)
            return_code = subprocess.call(command, shell=True)
            print("Download completed.\n")
        else:
            print(f"\n\n!!!  WARNING: No compatible extensions found for {package['name']}  !!!")
