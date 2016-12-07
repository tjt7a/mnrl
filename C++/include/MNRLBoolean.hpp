// Kevin Angstadt
// angstadt {at} virginia.edu
//
// MNRLBoolean Object

#ifndef MNRLUPCOUNTER_HPP
#define MNRLUPCOUNTER_HPP

#include <string>
#include <utility>
#include <vector>
#include <map>
#include <json11.hpp>

#include "MNRLDefs.hpp"
#include "MNRLNode.hpp"
#include "MNRLPort.hpp"

namespace MNRL {
	class MNRLDefs;
	class MNRLNode;
	class MNRLPort;
	class MNRLBoolean : public MNRLNode {
		public:
			MNRLBoolean (
				MNRLDefs::BooleanMode mode,
				int portCount,
				std::string id,
				MNRLDefs::EnableType enable,
				bool report,
				int reportId,
				std::shared_ptr<json11::Json::object> attributes
			);
			virtual ~MNRLBoolean();

			virtual json11::Json to_json();

		protected:
			int threshold;
			MNRLDefs::BooleanMode mode;
			int reportId;

		private:
			static port_def gen_input(int port_count) {
				port_def in;
				for(int i=0; i<port_count; ++i) {
					in.push_back(
						std::shared_ptr<MNRLPort>( new MNRLPort(
								"b" + std::to_string(i),
								1
							)
						)
					);
				}
				return in;
			}
			static port_def gen_output() {
				port_def outs;
				outs.push_back(
					std::shared_ptr<MNRLPort>( new MNRLPort(
							MNRLDefs::BOOLEAN_OUTPUT,
							1
						)
					)
				);
				return outs;
			}
	};
}

#endif
