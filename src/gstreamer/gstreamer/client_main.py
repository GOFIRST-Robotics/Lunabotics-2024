import sys

from rqt_gui.main import Main


def main():
    main = Main()
    sys.exit(main.main(sys.argv, standalone="gstreamer.client.ClientPlugin"))


if __name__ == "__main__":
    main()
